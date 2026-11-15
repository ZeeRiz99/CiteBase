"""Worker loop: claim one job at a time, run its handler, record the outcome."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import socket
import time

import structlog

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_sessionmaker
from app.models import Job
from app.providers.email import build_email_sender
from app.providers.storage import build_storage
from app.worker import queue
from app.worker.context import PermanentJobError, WorkerContext
from app.worker.handlers import HANDLERS

log = structlog.get_logger("worker")
STALE_CHECK_SECONDS = 30


def worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


async def run_once(ctx: WorkerContext, wid: str) -> bool:
    """Process at most one job. Return True if a job was processed."""
    async with ctx.sessionmaker() as db:
        job_id = await queue.claim_next(db, wid)
        if job_id is None:
            return False
        job = await db.get(Job, job_id)
        if job is None:
            return False
        # End the read transaction now: handlers can run for minutes and use their own sessions.
        await db.commit()
        spec = HANDLERS.get(job.job_type)
        bound = log.bind(job_id=str(job.id), job_type=job.job_type, attempt=job.attempts)
        if spec is None:
            await queue.mark_failed(db, job, f"no handler for {job.job_type}", retryable=False)
            bound.error("job_unknown_type")
            return True
        try:
            await spec.run(job, ctx)
        except PermanentJobError as exc:
            await queue.mark_failed(db, job, str(exc), retryable=False)
            bound.error("job_failed_permanently", error=str(exc))
        except Exception as exc:
            await queue.mark_failed(db, job, f"{type(exc).__name__}: {exc}", retryable=True)
            bound.warning("job_failed_will_retry", error=f"{type(exc).__name__}: {exc}")
        else:
            await queue.mark_succeeded(db, job, scrub_payload=spec.scrub_payload_on_success)
            bound.info("job_succeeded")
        return True


async def run_forever(settings: Settings) -> None:
    engine = create_engine(settings)
    ctx = WorkerContext(
        settings=settings,
        sessionmaker=create_sessionmaker(engine),
        email_sender=build_email_sender(settings),
        storage=build_storage(settings),
    )
    wid = worker_id()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    log.info("worker_started", worker=wid)
    last_stale_check = 0.0
    try:
        while not stop.is_set():
            if time.monotonic() - last_stale_check > STALE_CHECK_SECONDS:
                async with ctx.sessionmaker() as db:
                    if recovered := await queue.requeue_stale(db):
                        log.warning("stale_jobs_requeued", count=recovered)
                last_stale_check = time.monotonic()
            try:
                processed = await run_once(ctx, wid)
            except Exception:
                log.exception("worker_iteration_failed")
                processed = False
            if not processed:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
    finally:
        await engine.dispose()
        log.info("worker_stopped", worker=wid)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "development")
    asyncio.run(run_forever(settings))
