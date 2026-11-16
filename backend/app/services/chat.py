"""Chat: conversations and question turns on top of the RAG engine.

A turn has two halves:

1. `prepare_*` runs before any byte is streamed, so every check (ownership, rate and token
   limits, provider configured, one turn at a time) can still fail as a normal JSON error. It
   saves the question and a `streaming` answer placeholder and commits.
2. `stream` drives `RagEngine.stream` and yields SSE bytes. It commits right after retrieval, so
   no transaction stays open while the model writes. Whatever happens next (finished, refused,
   provider error, or the user pressing Stop, which closes the connection) ends in `_finish`,
   which records the answer, its sources, usage and any unanswered question.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import anyio
import httpx
import structlog
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, Conflict, NotFound
from app.core.pricing import cost_usd
from app.core.rate_limit import RateLimiter, enforce
from app.ingestion.chunking import count_tokens
from app.models import (
    Conversation,
    EvidenceStrength,
    FeedbackRating,
    Message,
    MessageRole,
    MessageSource,
    MessageStatus,
    RefusalReason,
    UnansweredQuestion,
    UnansweredStatus,
    UsageEvent,
    UsageKind,
    Workspace,
)
from app.providers.http import ProviderError, ProviderNotConfigured
from app.providers.llm import LLMMessage, LLMUsage
from app.rag.citations import validate
from app.rag.engine import (
    AnswerResult,
    DoneEvent,
    MetaEvent,
    RagEngine,
    ReplaceEvent,
    SourceRef,
    TokenEvent,
)
from app.rag.factory import build_engine
from app.repositories import chat as repo
from app.repositories import system as system_repo
from app.schemas.chat import MessageOut, SourceOut

log = structlog.get_logger("chat")

EngineFactory = Callable[[AsyncSession, Settings, Workspace, httpx.AsyncClient], RagEngine]
DEFAULT_TITLE = "New conversation"
PROVIDER_ERROR_TEXT = "The AI service did not respond. Please try again in a moment."


class UsageLimitReached(AppError):
    status_code = 429
    code = "usage_limit_reached"
    message = "This workspace has used its monthly AI allowance. An admin can raise the limit."


class AiNotConfigured(AppError):
    status_code = 503
    code = "ai_not_configured"
    message = "Answering is not set up yet: no AI provider key is configured on the server."


class QuestionTooLong(AppError):
    status_code = 422
    code = "question_too_long"


def sse(event: str, data: Any) -> bytes:
    """One Server-Sent Event. JSON never contains a raw newline, so one data line suffices."""
    payload = json.dumps(jsonable_encoder(data), separators=(",", ":"), ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode()


def title_from(question: str, limit: int = 60) -> str:
    text = " ".join(question.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return cut.rstrip(",.;:") + "..."


@dataclass
class Actor:
    user_id: uuid.UUID
    workspace: Workspace


@dataclass
class Turn:
    conversation_id: uuid.UUID
    answer_id: uuid.UUID
    question: str
    history: list[LLMMessage]
    engine: RagEngine


@dataclass
class _Progress:
    """What the stream has seen so far; `_finish` turns it into the stored answer."""

    started: float = field(default_factory=time.perf_counter)
    meta: MetaEvent | None = None
    parts: list[str] = field(default_factory=list)
    result: AnswerResult | None = None
    saved: MessageOut | None = None

    @property
    def text(self) -> str:
        return "".join(self.parts)


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        actor: Actor,
        *,
        http: httpx.AsyncClient,
        limiter: RateLimiter,
        engine_factory: EngineFactory = build_engine,
    ) -> None:
        self.db = db
        self.settings = settings
        self.actor = actor
        self.http = http
        self.limiter = limiter
        self.engine_factory = engine_factory

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.actor.workspace.id

    # Conversations -------------------------------------------------------------------------

    async def list_conversations(self, q: str | None, limit: int = 50) -> list[Conversation]:
        return await repo.list_conversations(
            self.db, self.workspace_id, self.actor.user_id, q=q, limit=limit
        )

    async def create_conversation(self, title: str | None) -> Conversation:
        conversation = Conversation(
            workspace_id=self.workspace_id,
            user_id=self.actor.user_id,
            title=(title or "").strip() or DEFAULT_TITLE,
        )
        self.db.add(conversation)
        await self.db.commit()
        return conversation

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await repo.get_conversation(
            self.db, self.workspace_id, self.actor.user_id, conversation_id
        )
        if conversation is None:
            raise NotFound()
        return conversation

    async def thread(self, conversation_id: uuid.UUID) -> tuple[Conversation, list[MessageOut]]:
        conversation = await self.get_conversation(conversation_id)
        messages = await repo.list_messages(self.db, conversation.id)
        ids = [m.id for m in messages]
        sources = await repo.sources_for(self.db, ids)
        feedback = await repo.feedback_for(self.db, ids, self.actor.user_id)
        return conversation, [
            MessageOut.build(m, sources.get(m.id, []), feedback.get(m.id)) for m in messages
        ]

    async def rename(self, conversation_id: uuid.UUID, title: str) -> Conversation:
        conversation = await self.get_conversation(conversation_id)
        conversation.title = title
        await self.db.commit()
        return conversation

    async def delete(self, conversation_id: uuid.UUID) -> None:
        conversation = await self.get_conversation(conversation_id)
        conversation.deleted_at = datetime.now(UTC)
        await self.db.commit()

    # Turns ---------------------------------------------------------------------------------

    async def _check_limits(self) -> None:
        await enforce(
            self.limiter, f"chat:user:{self.actor.user_id}", self.settings.chat_rate_per_minute, 60
        )
        limit = self.token_limit()
        if limit is not None:
            used = await repo.tokens_since(self.db, self.workspace_id, repo.month_start())
            if used >= limit:
                raise UsageLimitReached()

    def token_limit(self) -> int | None:
        own = self.actor.workspace.monthly_token_limit
        limit = own if own is not None else self.settings.monthly_token_limit
        return limit or None  # 0 = unlimited

    def _engine(self) -> RagEngine:
        try:
            return self.engine_factory(self.db, self.settings, self.actor.workspace, self.http)
        except ProviderNotConfigured as exc:
            raise AiNotConfigured() from exc

    async def _history(self, conversation_id: uuid.UUID, before: datetime) -> list[LLMMessage]:
        rows = await repo.history(
            self.db, conversation_id, before=before, limit=self.settings.chat_history_turns
        )
        return [
            LLMMessage("user" if m.role == MessageRole.user else "assistant", m.content)
            for m in rows
            if m.content
        ]

    async def prepare_ask(self, conversation_id: uuid.UUID, question: str) -> Turn:
        if len(question) > self.settings.max_question_chars:
            raise QuestionTooLong(
                f"Questions can be at most {self.settings.max_question_chars} characters."
            )
        conversation = await self.get_conversation(conversation_id)
        if await repo.has_streaming_message(self.db, conversation.id):
            raise Conflict("An answer is still being written in this conversation.")
        await self._check_limits()
        engine = self._engine()
        history = await self._history(conversation.id, datetime.now(UTC))

        user_message = Message(
            workspace_id=self.workspace_id,
            conversation_id=conversation.id,
            role=MessageRole.user,
            content=question,
            status=MessageStatus.complete,
        )
        self.db.add(user_message)
        await self.db.flush()  # the answer must sort after the question
        answer = Message(
            workspace_id=self.workspace_id,
            conversation_id=conversation.id,
            role=MessageRole.assistant,
            status=MessageStatus.streaming,
        )
        self.db.add(answer)
        if conversation.title == DEFAULT_TITLE and not history:
            conversation.title = title_from(question)
        conversation.updated_at = datetime.now(UTC)
        await self.db.commit()
        return Turn(conversation.id, answer.id, question, history, engine)

    async def prepare_regenerate(self, message_id: uuid.UUID) -> Turn:
        owned = await repo.get_owned_message(
            self.db, self.workspace_id, self.actor.user_id, message_id
        )
        if owned is None or owned[0].role != MessageRole.assistant:
            raise NotFound()
        old, conversation = owned
        latest = await repo.latest_visible_message(self.db, conversation.id)
        if latest is None or latest.id != old.id or old.status == MessageStatus.streaming:
            raise Conflict("Only the latest finished answer can be regenerated.")
        question = await repo.previous_user_message(self.db, old)
        if question is None:
            raise NotFound()
        await self._check_limits()
        engine = self._engine()
        history = await self._history(conversation.id, question.created_at)
        answer = Message(
            workspace_id=self.workspace_id,
            conversation_id=conversation.id,
            role=MessageRole.assistant,
            status=MessageStatus.streaming,
            regenerated_from_id=old.id,
        )
        self.db.add(answer)
        conversation.updated_at = datetime.now(UTC)
        await self.db.commit()
        return Turn(conversation.id, answer.id, question.content, history, engine)

    async def stream(self, turn: Turn) -> AsyncIterator[bytes]:
        progress = _Progress()
        try:
            async with aclosing(turn.engine.stream(turn.question, turn.history)) as events:
                async for event in events:
                    if isinstance(event, MetaEvent):
                        progress.meta = event
                        # Retrieval is done; do not hold a transaction while the model writes.
                        await self.db.commit()
                        yield sse(
                            "meta",
                            {
                                "conversation_id": turn.conversation_id,
                                "message_id": turn.answer_id,
                                "evidence": event.evidence,
                                "sources": [SourceOut.from_ref(s) for s in event.sources],
                            },
                        )
                    elif isinstance(event, TokenEvent):
                        progress.parts.append(event.text)
                        yield sse("token", {"text": event.text})
                    elif isinstance(event, ReplaceEvent):
                        progress.parts = [event.text]
                        yield sse("replace", {"text": event.text})
                    elif isinstance(event, DoneEvent):
                        progress.result = event.result
            result = progress.result
            assert result is not None
            saved = await self._finish(turn, progress)
            if result.refused:
                yield sse("refusal", {"text": result.text, "reason": result.refusal_reason})
            else:
                yield sse(
                    "citations",
                    {
                        "evidence": result.evidence,
                        "citations": [s for s in saved.sources if s.cited],
                    },
                )
            yield sse("done", {"message": saved})
        except ProviderError as exc:
            log.warning("chat_provider_error", provider=exc.provider, status=exc.status)
            saved = await self._finish(turn, progress, error=True)
            yield sse("error", {"code": "provider_error", "message": PROVIDER_ERROR_TEXT})
            yield sse("done", {"message": saved})
        except Exception:
            log.exception("chat_turn_failed")
            saved = await self._finish(turn, progress, error=True)
            yield sse("error", {"code": "internal_error", "message": PROVIDER_ERROR_TEXT})
            yield sse("done", {"message": saved})
        finally:
            if progress.saved is None:
                # The client went away (Stop button, closed tab) or we were cancelled.
                with anyio.CancelScope(shield=True):
                    try:
                        await self._finish(turn, progress, stopped=True)
                    except Exception:  # already logged; never mask the original exit
                        log.warning("chat_stop_not_recorded", message_id=str(turn.answer_id))

    # Recording -----------------------------------------------------------------------------

    async def _finish(
        self, turn: Turn, progress: _Progress, *, stopped: bool = False, error: bool = False
    ) -> MessageOut:
        if progress.saved is not None:
            return progress.saved
        try:
            saved = await self._record(turn, progress, stopped=stopped, error=error)
        except Exception:
            log.exception("chat_record_failed", message_id=str(turn.answer_id))
            await self.db.rollback()
            raise
        progress.saved = saved
        return saved

    async def _record(
        self, turn: Turn, progress: _Progress, *, stopped: bool, error: bool
    ) -> MessageOut:
        if stopped or error:
            await self.db.rollback()  # a cancelled query may have left the transaction broken
        answer = await self.db.get(Message, turn.answer_id)
        if answer is None:  # conversation deleted meanwhile
            raise NotFound()
        meta, result = progress.meta, progress.result
        engine = turn.engine
        sources: list[SourceRef] = meta.sources if meta else []

        if result is not None and not error:
            answer.content = result.text
            answer.status = MessageStatus.refused if result.refused else MessageStatus.complete
            answer.refusal_reason = (
                RefusalReason(result.refusal_reason) if result.refusal_reason else None
            )
            trace = result.trace()
            usage = list(result.usage)
            estimated = False
        else:
            # Stopped or failed mid-answer: keep the partial text with its valid citations only.
            check = validate(progress.text, {s.number for s in sources})
            for s in sources:
                s.cited = s.number in check.cited
            answer.content = check.text.strip()
            answer.status = MessageStatus.error if error else MessageStatus.stopped
            trace = self._partial_trace(meta)
            usage = list(meta.usage) if meta else []
            estimated = not any(u.kind == "chat" for u in usage) and bool(progress.parts)
            if estimated:
                usage.append(self._estimate_usage(engine, turn.question, sources, progress.text))

        trace["thresholds"] = asdict(engine.thresholds)
        trace["embedding_profile"] = engine.profile.key
        answer.retrieval_trace = trace
        answer.standalone_query = meta.standalone_query if meta else None
        answer.evidence_strength = EvidenceStrength(meta.evidence) if meta else None
        answer.prompt_version = result.prompt_version if result else trace.get("prompt_version")
        answer.llm_provider = getattr(engine.llm, "name", None)
        answer.llm_model = getattr(engine.llm, "model", None)
        answer_usage = [u for u in usage if u.kind in ("chat", "regenerate")]
        answer.input_tokens = sum(u.input_tokens for u in answer_usage) or None
        answer.output_tokens = sum(u.output_tokens for u in answer_usage) or None
        answer.latency_ms = int((time.perf_counter() - progress.started) * 1000)

        rows = [
            MessageSource(
                workspace_id=self.workspace_id,
                message_id=answer.id,
                source_number=s.number,
                chunk_id=s.chunk_id,
                document_id=s.document_id,
                document_version_id=s.document_version_id,
                document_title=s.document_title,
                section_title=s.section_title,
                location=s.location[:200],
                page_start=s.page_start,
                page_end=s.page_end,
                snippet=s.snippet,
                vector_score=s.vector_score,
                keyword_score=s.keyword_score,
                fused_score=s.fused_score,
                cited=s.cited,
            )
            for s in sources
        ]
        self.db.add_all(rows)
        for u in usage:
            self.db.add(self._usage_event(answer.id, engine, u, estimated=estimated))

        if answer.status == MessageStatus.refused and answer.refusal_reason is not None:
            self.db.add(
                UnansweredQuestion(
                    workspace_id=self.workspace_id,
                    message_id=answer.id,
                    user_id=self.actor.user_id,
                    question=turn.question,
                    reason=answer.refusal_reason,
                    status=UnansweredStatus.open,
                )
            )
            system_repo.add_event(
                self.db,
                workspace_id=self.workspace_id,
                event_type="question.unanswered",
                payload={"message_id": str(answer.id), "reason": answer.refusal_reason.value},
            )
        await self.db.commit()
        log.info(
            "chat_turn",
            message_id=str(answer.id),
            status=answer.status.value,
            evidence=answer.evidence_strength.value if answer.evidence_strength else None,
            latency_ms=answer.latency_ms,
        )
        return MessageOut.build(answer, rows)

    @staticmethod
    def _partial_trace(meta: MetaEvent | None) -> dict[str, Any]:
        if meta is None:
            return {"note": "stopped before retrieval finished"}
        return {
            "standalone_query": meta.standalone_query,
            "evidence": meta.evidence,
            "refusal_reason": None,
            "signals": meta.signals.as_dict(),
            "sources": [
                {
                    "number": s.number,
                    "chunk_id": str(s.chunk_id),
                    "document_title": s.document_title,
                    "location": s.location,
                    "vector_score": s.vector_score,
                    "keyword_score": s.keyword_score,
                    "fused_score": s.fused_score,
                    "cited": s.cited,
                }
                for s in meta.sources
            ],
            "usage": [asdict(u) for u in meta.usage],
            "timings_ms": {k: round(v, 1) for k, v in meta.timings_ms.items()},
            "stopped": True,
        }

    @staticmethod
    def _estimate_usage(
        engine: RagEngine, question: str, sources: list[SourceRef], partial: str
    ) -> LLMUsage:
        """The provider reports usage only at the end of a stream; estimate a stopped one."""
        prompt = question + "".join(s.snippet for s in sources)
        return LLMUsage(
            model=getattr(engine.llm, "model", "unknown"),
            input_tokens=count_tokens(prompt),
            output_tokens=count_tokens(partial),
            kind="chat",
        )

    def _usage_event(
        self, message_id: uuid.UUID, engine: RagEngine, usage: LLMUsage, *, estimated: bool
    ) -> UsageEvent:
        cost = cost_usd(usage.model, usage.input_tokens, usage.output_tokens)
        kind = UsageKind(usage.kind) if usage.kind in UsageKind.__members__ else UsageKind.chat
        return UsageEvent(
            workspace_id=self.workspace_id,
            user_id=self.actor.user_id,
            message_id=message_id,
            kind=kind,
            provider=getattr(engine.llm, "name", "unknown"),
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated=estimated and usage.kind == "chat",
            cost_usd=Decimal(str(round(cost, 6))) if cost is not None else None,
        )

    # Feedback ------------------------------------------------------------------------------

    async def _owned_answer(self, message_id: uuid.UUID) -> Message:
        owned = await repo.get_owned_message(
            self.db, self.workspace_id, self.actor.user_id, message_id
        )
        if owned is None or owned[0].role != MessageRole.assistant:
            raise NotFound()
        return owned[0]

    async def set_feedback(
        self, message_id: uuid.UUID, rating: FeedbackRating, comment: str | None
    ) -> None:
        answer = await self._owned_answer(message_id)
        if answer.status == MessageStatus.streaming:
            raise Conflict("Wait for the answer to finish before rating it.")
        await repo.upsert_feedback(
            self.db,
            workspace_id=self.workspace_id,
            message_id=answer.id,
            user_id=self.actor.user_id,
            rating=rating,
            comment=(comment or "").strip() or None,
        )
        system_repo.add_event(
            self.db,
            workspace_id=self.workspace_id,
            event_type="feedback.received",
            payload={"message_id": str(answer.id), "rating": rating.value},
        )
        await self.db.commit()

    async def clear_feedback(self, message_id: uuid.UUID) -> None:
        answer = await self._owned_answer(message_id)
        await repo.delete_feedback(self.db, message_id=answer.id, user_id=self.actor.user_id)
        await self.db.commit()
