"""Job handlers. Each handler declares whether its payload is sensitive (scrubbed on success)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Job
from app.providers.email import EmailSender
from app.services import emails


class PermanentJobError(Exception):
    """The job can never succeed (bad payload, missing data). Do not retry."""


@dataclass(frozen=True)
class WorkerContext:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    email_sender: EmailSender


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
}
