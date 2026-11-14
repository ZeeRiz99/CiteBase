"""Audit log, domain-event outbox and the background job queue."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class AuditLog(UUIDPk, Base):
    """Append-only: the app role may INSERT and SELECT, never UPDATE or DELETE."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_workspace_created", "workspace_id", "created_at"),)
    # No INSERT ... RETURNING: rows with workspace_id NULL (e.g. failed logins) are insertable
    # but not readable under RLS, and RETURNING would require them to be readable.
    __mapper_args__ = {"eager_defaults": False}  # noqa: RUF012

    workspace_id: Mapped[uuid.UUID | None] = mapped_column()
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DomainEvent(UUIDPk, Base):
    """Transactional outbox. Written with the state change; dispatched later (webhooks in V3)."""

    __tablename__ = "domain_events"
    __table_args__ = (
        Index(
            "ix_domain_events_undispatched",
            "occurred_at",
            postgresql_where=text("dispatched_at IS NULL"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Job(UUIDPk, Base):
    """Database-backed job queue, claimed with FOR UPDATE SKIP LOCKED.

    Not under RLS: the worker must see every workspace's queue. Jobs carry ids only; the
    handler sets the tenant context before touching tenant data.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_claimable", "run_after", postgresql_where=text("status = 'queued'")),
    )

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), nullable=False, server_default=JobStatus.queued.value
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_by: Mapped[str | None] = mapped_column(String(80))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
