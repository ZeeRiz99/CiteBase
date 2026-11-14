"""Audit log, outbox events and job queue writes."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, DomainEvent, Job


def add_audit(
    db: AsyncSession,
    *,
    action: str,
    workspace_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_hash=ip_hash,
            details=details or {},
        )
    )


def add_event(
    db: AsyncSession, *, workspace_id: uuid.UUID, event_type: str, payload: dict[str, Any]
) -> None:
    db.add(DomainEvent(workspace_id=workspace_id, event_type=event_type, payload=payload))


def enqueue_job(
    db: AsyncSession,
    *,
    job_type: str,
    payload: dict[str, Any],
    workspace_id: uuid.UUID | None = None,
    max_attempts: int = 5,
) -> Job:
    job = Job(
        job_type=job_type, payload=payload, workspace_id=workspace_id, max_attempts=max_attempts
    )
    db.add(job)
    return job
