from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models import (
    Conversation,
    EvidenceStrength,
    Feedback,
    FeedbackRating,
    Message,
    MessageRole,
    MessageSource,
    MessageStatus,
    RefusalReason,
    UnansweredQuestion,
    UnansweredStatus,
)
from app.rag.engine import SourceRef

SNIPPET_CHARS = 600  # what the browser gets per source; the viewer loads the full passage


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def build(cls, c: Conversation) -> ConversationOut:
        return cls(id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be empty")
        return value


class SourceOut(BaseModel):
    number: int
    chunk_id: uuid.UUID | None
    document_id: uuid.UUID | None
    document_title: str
    section_title: str | None
    location: str
    page_start: int
    page_end: int
    snippet: str
    cited: bool
    available: bool  # False once the document was purged

    @classmethod
    def from_row(cls, s: MessageSource) -> SourceOut:
        return cls(
            number=s.source_number,
            chunk_id=s.chunk_id,
            document_id=s.document_id,
            document_title=s.document_title,
            section_title=s.section_title,
            location=s.location,
            page_start=s.page_start,
            page_end=s.page_end,
            snippet=s.snippet[:SNIPPET_CHARS],
            cited=s.cited,
            available=s.chunk_id is not None,
        )

    @classmethod
    def from_ref(cls, s: SourceRef) -> SourceOut:
        return cls(
            number=s.number,
            chunk_id=s.chunk_id,
            document_id=s.document_id,
            document_title=s.document_title,
            section_title=s.section_title,
            location=s.location,
            page_start=s.page_start,
            page_end=s.page_end,
            snippet=s.snippet[:SNIPPET_CHARS],
            cited=s.cited,
            available=True,
        )


class FeedbackOut(BaseModel):
    rating: FeedbackRating
    comment: str | None


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    status: MessageStatus
    refusal_reason: RefusalReason | None
    evidence: EvidenceStrength | None
    created_at: datetime
    regenerated_from_id: uuid.UUID | None
    sources: list[SourceOut]
    feedback: FeedbackOut | None

    @classmethod
    def build(
        cls, m: Message, sources: list[MessageSource], feedback: Feedback | None = None
    ) -> MessageOut:
        return cls(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            status=m.status,
            refusal_reason=m.refusal_reason,
            evidence=m.evidence_strength,
            created_at=m.created_at,
            regenerated_from_id=m.regenerated_from_id,
            # Cited sources first (in citation order), then the rest by rank.
            sources=[SourceOut.from_row(s) for s in sorted(sources, key=lambda s: not s.cited)],
            feedback=FeedbackOut(rating=feedback.rating, comment=feedback.comment)
            if feedback
            else None,
        )


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ask a question")
        return value


class FeedbackRequest(BaseModel):
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)


class TraceOut(BaseModel):
    message_id: uuid.UUID
    question: str | None
    standalone_query: str | None
    status: MessageStatus
    evidence: EvidenceStrength | None
    refusal_reason: RefusalReason | None
    prompt_version: str | None
    llm_provider: str | None
    llm_model: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    cost_usd: float | None
    trace: dict[str, Any]


class UnansweredOut(BaseModel):
    id: uuid.UUID
    question: str
    reason: RefusalReason
    status: UnansweredStatus
    message_id: uuid.UUID
    created_at: datetime

    @classmethod
    def build(cls, u: UnansweredQuestion) -> UnansweredOut:
        return cls(
            id=u.id,
            question=u.question,
            reason=u.reason,
            status=u.status,
            message_id=u.message_id,
            created_at=u.created_at,
        )


class UnansweredList(BaseModel):
    items: list[UnansweredOut]
    total: int
    page: int
    page_size: int


class UnansweredPatch(BaseModel):
    status: UnansweredStatus


class SuggestedQuestions(BaseModel):
    questions: list[str]


class UsageOut(BaseModel):
    period_start: datetime
    tokens_used: int
    token_limit: int | None  # None: unlimited
    cost_usd: float | None


class QuestionCounts(BaseModel):
    last_7d: int
    last_30d: int
    unanswered_open: int
    helpful_rate: float | None  # None until someone rates an answer
    rated: int
