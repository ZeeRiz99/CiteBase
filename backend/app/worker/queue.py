"""Database-backed job queue: claim, complete, retry with backoff, recover stale jobs."""

from __future__ import annotations

import random
import uuid
from datetime import timedelta

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobStatus
from app.repositories.users import utcnow

STALE_AFTER = timedelta(minutes=5)
MAX_BACKOFF_SECONDS = 300

_CLAIM_SQL = text(
    """
    UPDATE jobs
       SET status = 'running', attempts = attempts + 1, locked_by = :worker,
           locked_at = now(), heartbeat_at = now()
     WHERE id = (
            SELECT id FROM jobs
             WHERE status = 'queued' AND run_after <= now()
             ORDER BY run_after
             FOR UPDATE SKIP LOCKED
             LIMIT 1)
    RETURNING id
    """
)


async def claim_next(db: AsyncSession, worker_id: str) -> uuid.UUID | None:
    result = await db.execute(_CLAIM_SQL, {"worker": worker_id})
    job_id = result.scalar_one_or_none()
    await db.commit()
    return job_id


def backoff_seconds(attempts: int) -> float:
    base: float = min(MAX_BACKOFF_SECONDS, 5 * 2 ** max(0, attempts - 1))
    return base + random.uniform(0, 1)  # noqa: S311 - jitter, not security


async def mark_succeeded(db: AsyncSession, job: Job, *, scrub_payload: bool) -> None:
    job.status = JobStatus.succeeded
    job.finished_at = utcnow()
    job.last_error = None
    if scrub_payload:
        job.payload = {"scrubbed": True}
    await db.commit()


async def mark_failed(db: AsyncSession, job: Job, error: str, *, retryable: bool) -> None:
    job.last_error = error[:2000]
    job.locked_by = None
    if retryable and job.attempts < job.max_attempts:
        job.status = JobStatus.queued
        job.run_after = utcnow() + timedelta(seconds=backoff_seconds(job.attempts))
    else:
        job.status = JobStatus.failed
        job.finished_at = utcnow()
    await db.commit()


async def requeue_stale(db: AsyncSession) -> int:
    """Jobs whose worker died mid-run go back to the queue (their attempt is already counted)."""
    result = await db.execute(
        update(Job)
        .where(Job.status == JobStatus.running, Job.heartbeat_at < utcnow() - STALE_AFTER)
        .values(status=JobStatus.queued, locked_by=None, run_after=utcnow())
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
