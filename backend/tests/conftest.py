"""Test fixtures: a real Postgres (pgvector image) database, migrated once per session and
truncated before every test. External services are replaced by in-memory fakes."""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.main import create_app
from app.providers.email import MemoryEmailSender, OutgoingEmail
from app.worker.context import WorkerContext
from app.worker.runner import run_once

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
TEST_MIGRATIONS_DATABASE_URL = os.environ.get("TEST_MIGRATIONS_DATABASE_URL", "")
TABLES = (
    "chunks",
    "document_pages",
    "document_versions",
    "documents",
    "jobs",
    "domain_events",
    "audit_log",
    "collections",
    "memberships",
    "workspaces",
    "auth_tokens",
    "auth_sessions",
    "users",
)
TEST_SECRET = "test-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[None]:
    if not TEST_DATABASE_URL or not TEST_MIGRATIONS_DATABASE_URL:
        pytest.exit("TEST_DATABASE_URL and TEST_MIGRATIONS_DATABASE_URL must be set", returncode=2)
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = TEST_MIGRATIONS_DATABASE_URL
    command.downgrade(cfg, "base")  # also exercises every downgrade path
    command.upgrade(cfg, "head")
    yield


@pytest.fixture
def owner_engine(migrated_db: None) -> Iterator[Any]:
    """Table-owner connection for setup and assertions (still subject to FORCE RLS)."""
    # A leaked transaction holding locks makes tests fail fast instead of hanging.
    engine = create_engine(
        TEST_MIGRATIONS_DATABASE_URL, connect_args={"options": "-c lock_timeout=5s"}
    )
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(owner_engine: Any) -> None:
    with owner_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=TEST_DATABASE_URL,
        secret_key=TEST_SECRET,  # type: ignore[arg-type]
        cookie_secure=False,
        email_backend="memory",
        app_base_url="http://testserver",
        storage_dir=str(tmp_path / "storage"),
        extraction_timeout_seconds=60,
        # Deterministic, offline AI providers: tests never call real APIs or spend money.
        embedding_backend="fake",
        llm_backend="fake",
        gemini_api_key=None,
        openai_api_key=None,
        anthropic_api_key=None,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


class Api:
    """Test client that behaves like the frontend: fetches and sends the CSRF token."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    @property
    def cookies(self) -> httpx.Cookies:
        return self.client.cookies

    async def _csrf(self) -> str:
        token = self.client.cookies.get("cb_csrf")
        if token:
            return str(token)
        response = await self.client.get("/api/v1/auth/csrf")
        return str(response.json()["csrf_token"])

    async def get(self, url: str) -> httpx.Response:
        return await self.client.get(url)

    async def send(self, method: str, url: str, json: Any = None) -> httpx.Response:
        headers = {"X-CSRF-Token": await self._csrf()}
        return await self.client.request(method, url, json=json, headers=headers)

    async def post(self, url: str, json: Any = None) -> httpx.Response:
        return await self.send("POST", url, json)

    async def patch(self, url: str, json: Any = None) -> httpx.Response:
        return await self.send("PATCH", url, json)

    async def delete(self, url: str) -> httpx.Response:
        return await self.send("DELETE", url)

    async def upload(
        self,
        filename: str,
        content: bytes,
        url: str = "/api/v1/documents",
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        headers = {"X-CSRF-Token": await self._csrf()}
        return await self.client.post(
            url, files={"file": (filename, content)}, data=data or {}, headers=headers
        )

    async def register(
        self,
        email: str = "ada@example.com",
        password: str = "correct-horse-battery",
        name: str = "Ada Lovelace",
    ) -> httpx.Response:
        return await self.post(
            "/api/v1/auth/register",
            {
                "full_name": name,
                "email": email,
                "password": password,
                "workspace_name": f"{name} Co",
            },
        )

    async def login(self, email: str, password: str) -> httpx.Response:
        return await self.post("/api/v1/auth/login", {"email": email, "password": password})


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[Api]:
    async with _client(app) as client:
        yield Api(client)


@pytest.fixture
async def api_b(app: FastAPI) -> AsyncIterator[Api]:
    """A second, independent browser (separate cookie jar)."""
    async with _client(app) as client:
        yield Api(client)


class Mailbox:
    """Runs queued jobs in-process (the real worker code) and captures sent email."""

    def __init__(self, app: FastAPI, settings: Settings) -> None:
        self.sender = MemoryEmailSender()
        self.ctx = WorkerContext(
            settings=settings,
            sessionmaker=app.state.sessionmaker,
            email_sender=self.sender,
            storage=app.state.storage,
            http=httpx.AsyncClient(),
        )

    async def drain(self) -> int:
        """Run due jobs until none are left. Returns how many ran."""
        count = 0
        while await run_once(self.ctx, "test-worker"):
            count += 1
        return count

    async def deliver(self) -> list[OutgoingEmail]:
        """Run the worker until the queue is empty, then return everything sent so far."""
        await self.drain()
        return self.sender.outbox

    @staticmethod
    def token_from(message: OutgoingEmail) -> str:
        match = re.search(r"token=([A-Za-z0-9_\-]+)", message.text)
        assert match, f"no token link in email: {message.text}"
        return match.group(1)


@pytest.fixture
def mailbox(app: FastAPI, settings: Settings) -> Mailbox:
    return Mailbox(app, settings)
