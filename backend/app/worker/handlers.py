"""Job handler registry. Handlers with sensitive payloads have them scrubbed on success."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.ingestion.pipeline import ingest_document, purge_document
from app.models import Job
from app.services import emails
from app.worker.context import PermanentJobError, WorkerContext

Handler = Callable[[Job, WorkerContext], Awaitable[None]]


@dataclass(frozen=True)
class HandlerSpec:
    run: Handler
    scrub_payload_on_success: bool = False


async def send_email(job: Job, ctx: WorkerContext) -> None:
    try:
        message = emails.render(job.payload["template"], job.payload["context"], ctx.settings)
    except (KeyError, ValueError) as exc:
        raise PermanentJobError(f"invalid email payload: {exc}") from exc
    await ctx.email_sender.send(message)


HANDLERS: dict[str, HandlerSpec] = {
    # Email payloads contain one-time links, so they are wiped once sent.
    "send_email": HandlerSpec(run=send_email, scrub_payload_on_success=True),
    "ingest": HandlerSpec(run=ingest_document),
    "purge_document": HandlerSpec(run=purge_document),
}

__all__ = ["HANDLERS", "HandlerSpec", "PermanentJobError", "WorkerContext"]
