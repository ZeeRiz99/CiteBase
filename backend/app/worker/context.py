"""Shared worker dependencies and the job heartbeat."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Job
from app.providers.email import EmailSender
from app.providers.storage import Storage
from app.repositories.users import utcnow

HEARTBEAT_SECONDS = 30


class PermanentJobError(Exception):
    """The job can never succeed (bad payload, missing data). Do not retry."""


@dataclass(frozen=True)
class WorkerContext:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    email_sender: EmailSender
    storage: Storage


async def touch(maker: async_sessionmaker[AsyncSession], job_id: uuid.UUID) -> None:
    async with maker() as db:
        await db.execute(update(Job).where(Job.id == job_id).values(heartbeat_at=utcnow()))
        await db.commit()


@contextlib.asynccontextmanager
async def heartbeat(ctx: WorkerContext, job_id: uuid.UUID) -> AsyncIterator[None]:
    """Refresh the job's heartbeat while a long step runs, so it is not reclaimed as stale."""

    async def beat() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            with contextlib.suppress(Exception):
                await touch(ctx.sessionmaker, job_id)

    task = asyncio.create_task(beat())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
