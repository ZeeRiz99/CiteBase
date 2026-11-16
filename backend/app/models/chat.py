"""Chat: conversations, messages and the passages behind each answer; feedback; usage."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class MessageRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"


class MessageStatus(enum.StrEnum):
    streaming = "streaming"
    complete = "complete"
    stopped = "stopped"
    refused = "refused"
    error = "error"


class RefusalReason(enum.StrEnum):
    gate = "gate"
    model = "model"
    no_valid_citation = "no_valid_citation"


class EvidenceStrength(enum.StrEnum):
    strong = "strong"
    partial = "partial"
    weak = "weak"


class FeedbackRating(enum.StrEnum):
    helpful = "helpful"
    not_helpful = "not_helpful"


class UnansweredStatus(enum.StrEnum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class UsageKind(enum.StrEnum):
    chat = "chat"
    rewrite = "rewrite"
    regenerate = "regenerate"
    suggest = "suggest"


def _enum(cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Conversation(UUIDPk, Timestamps, Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_owner", "workspace_id", "user_id", "updated_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(UUIDPk, Timestamps, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_thread", "conversation_id", "created_at"),
        Index("ix_messages_workspace_created", "workspace_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(_enum(MessageRole, "message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    standalone_query: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MessageStatus] = mapped_column(
        _enum(MessageStatus, "message_status"), nullable=False
    )
    refusal_reason: Mapped[RefusalReason | None] = mapped_column(
        _enum(RefusalReason, "refusal_reason")
    )
    evidence_strength: Mapped[EvidenceStrength | None] = mapped_column(
        _enum(EvidenceStrength, "evidence_strength")
    )
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    llm_provider: Mapped[str | None] = mapped_column(String(40))
    llm_model: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retrieval_trace: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    regenerated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )


class MessageSource(UUIDPk, Base):
    """Every passage shown to the model for an answer; `cited` marks the validated ones."""

    __tablename__ = "message_sources"
    __table_args__ = (
        UniqueConstraint("message_id", "source_number", name="uq_message_sources_message_id"),
        Index("ix_message_sources_document_id", "document_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    source_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    document_version_id: Mapped[uuid.UUID | None] = mapped_column()
    document_title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_title: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    vector_score: Mapped[float | None] = mapped_column(Float)
    keyword_score: Mapped[float | None] = mapped_column(Float)
    fused_score: Mapped[float] = mapped_column(Float, nullable=False)
    cited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class Feedback(UUIDPk, Timestamps, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_feedback_message_id"),
        Index("ix_feedback_workspace_id", "workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[FeedbackRating] = mapped_column(
        _enum(FeedbackRating, "feedback_rating"), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text)


class UnansweredQuestion(UUIDPk, Timestamps, Base):
    __tablename__ = "unanswered_questions"
    __table_args__ = (
        Index("ix_unanswered_questions_queue", "workspace_id", "status", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[RefusalReason] = mapped_column(
        _enum(RefusalReason, "refusal_reason"), nullable=False
    )
    status: Mapped[UnansweredStatus] = mapped_column(
        _enum(UnansweredStatus, "unanswered_status"),
        nullable=False,
        server_default=UnansweredStatus.open.value,
    )


class UsageEvent(UUIDPk, Base):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_workspace_created", "workspace_id", "created_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    kind: Mapped[UsageKind] = mapped_column(_enum(UsageKind, "usage_kind"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
