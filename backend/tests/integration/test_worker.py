from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import select, text

from app.core.config import Settings
from app.models import Job, JobStatus
from app.providers.email import OutgoingEmail
from app.repositories.system import enqueue_job
from app.repositories.users import utcnow
from app.worker import queue
from app.worker.context import WorkerContext
from app.worker.runner import run_once

EMAIL_PAYLOAD = {
    "template": "verify_email",
    "context": {"to": "x@example.com", "name": "X", "link": "http://t/verify-email?token=abc"},
}


class FlakySender:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.sent: list[OutgoingEmail] = []

    async def send(self, message: OutgoingEmail) -> None:
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionError("smtp down")
        self.sent.append(message)


async def _enqueue(app: FastAPI, job_type: str, payload: dict[str, Any]) -> None:
    async with app.state.sessionmaker() as db:
        enqueue_job(db, job_type=job_type, payload=payload)
        await db.commit()


async def _job(app: FastAPI) -> Job:
    async with app.state.sessionmaker() as db:
        return (await db.execute(select(Job))).scalar_one()


def _ctx(app: FastAPI, settings: Settings, sender: Any) -> WorkerContext:
    return WorkerContext(
        settings=settings,
        sessionmaker=app.state.sessionmaker,
        email_sender=sender,
        storage=app.state.storage,
        http=httpx.AsyncClient(),
    )


async def test_successful_email_job_scrubs_its_payload(app: FastAPI, settings: Settings) -> None:
    sender = FlakySender(failures=0)
    await _enqueue(app, "send_email", EMAIL_PAYLOAD)
    assert await run_once(_ctx(app, settings, sender), "w1")
    job = await _job(app)
    assert job.status == JobStatus.succeeded
    assert job.payload == {"scrubbed": True}
    assert len(sender.sent) == 1


async def test_transient_failure_is_retried_with_backoff(
    app: FastAPI, settings: Settings, owner_engine: Any
) -> None:
    sender = FlakySender(failures=1)
    ctx = _ctx(app, settings, sender)
    await _enqueue(app, "send_email", EMAIL_PAYLOAD)

    assert await run_once(ctx, "w1")
    job = await _job(app)
    assert job.status == JobStatus.queued
    assert job.attempts == 1
    assert "smtp down" in (job.last_error or "")
    assert job.run_after > utcnow()
    assert not await run_once(ctx, "w1")  # not due yet

    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE jobs SET run_after = now()"))
    assert await run_once(ctx, "w1")
    assert (await _job(app)).status == JobStatus.succeeded


async def test_bad_payload_fails_permanently(app: FastAPI, settings: Settings) -> None:
    await _enqueue(app, "send_email", {"template": "nope", "context": {"to": "x", "link": "y"}})
    assert await run_once(_ctx(app, settings, FlakySender(0)), "w1")
    job = await _job(app)
    assert job.status == JobStatus.failed
    assert job.attempts == 1


async def test_unknown_job_type_fails_permanently(app: FastAPI, settings: Settings) -> None:
    await _enqueue(app, "does_not_exist", {})
    assert await run_once(_ctx(app, settings, FlakySender(0)), "w1")
    assert (await _job(app)).status == JobStatus.failed


async def test_stale_running_jobs_are_requeued(app: FastAPI, owner_engine: Any) -> None:
    await _enqueue(app, "send_email", EMAIL_PAYLOAD)
    with owner_engine.begin() as conn:
        conn.execute(
            text("UPDATE jobs SET status = 'running', heartbeat_at = now() - :d"),
            {"d": timedelta(minutes=10)},
        )
    async with app.state.sessionmaker() as db:
        assert await queue.requeue_stale(db) == 1
    assert (await _job(app)).status == JobStatus.queued


def test_backoff_grows_and_is_capped() -> None:
    assert 5 <= queue.backoff_seconds(1) < 6
    assert 10 <= queue.backoff_seconds(2) < 11
    assert queue.backoff_seconds(20) < queue.MAX_BACKOFF_SECONDS + 1
