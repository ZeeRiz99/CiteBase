"""Workspace isolation: repository scoping plus Postgres row-level security as a second line."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.security import AccessClaims, create_access_token, decode_access_token
from app.db.session import set_tenant
from app.models import Collection, Membership, Workspace
from tests.conftest import TEST_DATABASE_URL, Api


async def _ids(api: Api) -> tuple[uuid.UUID, uuid.UUID]:
    me = (await api.get("/api/v1/auth/me")).json()
    return uuid.UUID(me["user"]["id"]), uuid.UUID(me["workspace"]["id"])


@pytest.fixture
async def two_tenants(api: Api, api_b: Api) -> dict[str, tuple[uuid.UUID, uuid.UUID]]:
    await api.register(email="a@example.com", name="Alice A")
    await api_b.register(email="b@example.com", name="Bob B")
    return {"a": await _ids(api), "b": await _ids(api_b)}


@pytest.fixture
async def app_sessions() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_rls_shows_only_the_current_workspace(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]],
    app_sessions: async_sessionmaker[AsyncSession],
) -> None:
    user_a, ws_a = two_tenants["a"]
    _, ws_b = two_tenants["b"]
    async with app_sessions() as db:
        await set_tenant(db, workspace_id=ws_a, user_id=user_a)
        # Deliberately unfiltered queries: RLS alone must hide workspace B.
        workspaces = (await db.execute(select(Workspace.id))).scalars().all()
        collections = (await db.execute(select(Collection.workspace_id))).scalars().all()
        memberships = (await db.execute(select(Membership.workspace_id))).scalars().all()
    assert workspaces == [ws_a]
    assert set(collections) == {ws_a}
    assert set(memberships) == {ws_a}
    assert ws_b not in workspaces


async def test_rls_fails_closed_without_context(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]],
    app_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with app_sessions() as db:
        assert (await db.execute(select(Collection))).scalars().all() == []
        assert (await db.execute(select(Workspace))).scalars().all() == []


async def test_rls_blocks_writes_into_another_workspace(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]],
    app_sessions: async_sessionmaker[AsyncSession],
) -> None:
    user_a, ws_a = two_tenants["a"]
    _, ws_b = two_tenants["b"]
    async with app_sessions() as db:
        await set_tenant(db, workspace_id=ws_a, user_id=user_a)
        db.add(Collection(workspace_id=ws_b, name="Injected"))
        with pytest.raises((ProgrammingError, DBAPIError), match="row-level security"):
            await db.flush()


async def test_tenant_context_does_not_leak_through_the_pool(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]],
) -> None:
    user_a, ws_a = two_tenants["a"]
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as db:
            await set_tenant(db, workspace_id=ws_a, user_id=user_a)
            assert (await db.execute(select(Collection))).scalars().all()
            await db.commit()
        async with maker() as db:  # same physical connection, no context set
            assert (await db.execute(select(Collection))).scalars().all() == []
            setting = (
                await db.execute(text("SELECT current_setting('app.workspace_id', true)"))
            ).scalar()
            assert not setting
    finally:
        await engine.dispose()


async def test_tenant_context_survives_commit_within_a_session(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]],
    app_sessions: async_sessionmaker[AsyncSession],
) -> None:
    user_a, ws_a = two_tenants["a"]
    async with app_sessions() as db:
        await set_tenant(db, workspace_id=ws_a, user_id=user_a)
        await db.commit()
        assert len((await db.execute(select(Collection))).scalars().all()) == 1


async def test_audit_log_is_append_only_for_the_app_role(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]],
    app_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with app_sessions() as db:
        with pytest.raises((ProgrammingError, DBAPIError), match="permission denied"):
            await db.execute(text("DELETE FROM audit_log"))


async def test_forged_workspace_claim_is_rejected(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]], api: Api, settings: Settings
) -> None:
    """A valid session for user A combined with workspace B's id must not grant access."""
    user_a, _ = two_tenants["a"]
    _, ws_b = two_tenants["b"]
    real = decode_access_token(settings, str(api.cookies.get("cb_access", path="/api")))
    assert real is not None
    forged = create_access_token(
        settings, AccessClaims(user_id=user_a, workspace_id=ws_b, session_id=real.session_id)
    )
    api.cookies.set("cb_access", forged, path="/api")
    assert (await api.get("/api/v1/auth/me")).status_code == 401


async def test_each_user_sees_only_their_own_workspace(
    two_tenants: dict[str, tuple[uuid.UUID, uuid.UUID]], api: Api, api_b: Api
) -> None:
    assert (await api.get("/api/v1/auth/me")).json()["workspace"]["id"] == str(two_tenants["a"][1])
    assert (await api_b.get("/api/v1/auth/me")).json()["workspace"]["id"] == str(
        two_tenants["b"][1]
    )
