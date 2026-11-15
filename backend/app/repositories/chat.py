"""Queries for conversations, messages, sources, feedback, unanswered questions and usage.

Every query is scoped by workspace (and, for conversations, by owner). RLS is the second line.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.ids import uuid7
from app.models import (
    Conversation,
    Feedback,
    FeedbackRating,
    Message,
    MessageRole,
    MessageSource,
    MessageStatus,
    UnansweredQuestion,
    UnansweredStatus,
    UsageEvent,
)


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def list_conversations(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID, *, q: str | None, limit: int
) -> list[Conversation]:
    stmt = select(Conversation).where(
        Conversation.workspace_id == workspace_id,
        Conversation.user_id == user_id,
        Conversation.deleted_at.is_(None),
    )
    if q:
        stmt = stmt.where(Conversation.title.ilike(_like(q), escape="\\"))
    stmt = stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars())


async def get_conversation(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation | None:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.workspace_id == workspace_id,
        Conversation.user_id == user_id,
        Conversation.deleted_at.is_(None),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _visible(conversation_id: uuid.UUID) -> Select[Message]:
    """Messages of a thread, minus answers that were regenerated (their successor replaces them)."""
    newer = aliased(Message)
    return select(Message).where(
        Message.conversation_id == conversation_id,
        ~exists().where(newer.regenerated_from_id == Message.id),
    )


async def list_messages(db: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    stmt = _visible(conversation_id).order_by(Message.created_at, Message.id)
    return list((await db.execute(stmt)).scalars())


async def history(
    db: AsyncSession, conversation_id: uuid.UUID, *, before: datetime, limit: int
) -> list[Message]:
    """The last `limit` finished messages before a turn, oldest first (for follow-up rewriting)."""
    if limit == 0:
        return []
    stmt = (
        _visible(conversation_id)
        .where(
            Message.created_at < before,
            Message.status.in_([MessageStatus.complete, MessageStatus.refused]),
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    return list(reversed(list((await db.execute(stmt)).scalars())))


async def sources_for(
    db: AsyncSession, message_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[MessageSource]]:
    out: dict[uuid.UUID, list[MessageSource]] = defaultdict(list)
    if not message_ids:
        return out
    stmt = (
        select(MessageSource)
        .where(MessageSource.message_id.in_(message_ids))
        .order_by(MessageSource.message_id, MessageSource.source_number)
    )
    for source in (await db.execute(stmt)).scalars():
        out[source.message_id].append(source)
    return out


async def feedback_for(
    db: AsyncSession, message_ids: list[uuid.UUID], user_id: uuid.UUID
) -> dict[uuid.UUID, Feedback]:
    if not message_ids:
        return {}
    stmt = select(Feedback).where(Feedback.message_id.in_(message_ids), Feedback.user_id == user_id)
    return {f.message_id: f for f in (await db.execute(stmt)).scalars()}


async def get_owned_message(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID, message_id: uuid.UUID
) -> tuple[Message, Conversation] | None:
    stmt = (
        select(Message, Conversation)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.id == message_id,
            Message.workspace_id == workspace_id,
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
    )
    row = (await db.execute(stmt)).one_or_none()
    return (row[0], row[1]) if row else None


async def get_message(
    db: AsyncSession, workspace_id: uuid.UUID, message_id: uuid.UUID
) -> Message | None:
    stmt = select(Message).where(Message.id == message_id, Message.workspace_id == workspace_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def previous_user_message(db: AsyncSession, answer: Message) -> Message | None:
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == answer.conversation_id,
            Message.role == MessageRole.user,
            Message.created_at <= answer.created_at,
            Message.id != answer.id,
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def latest_visible_message(db: AsyncSession, conversation_id: uuid.UUID) -> Message | None:
    stmt = _visible(conversation_id).order_by(Message.created_at.desc(), Message.id.desc()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def has_streaming_message(db: AsyncSession, conversation_id: uuid.UUID) -> bool:
    """A turn is in progress (or was cut off less than two minutes ago)."""
    stmt = select(
        exists().where(
            Message.conversation_id == conversation_id,
            Message.status == MessageStatus.streaming,
            Message.created_at > datetime.now(UTC) - timedelta(minutes=2),
        )
    )
    return bool((await db.execute(stmt)).scalar())


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def tokens_since(db: AsyncSession, workspace_id: uuid.UUID, since: datetime) -> int:
    stmt = select(
        func.coalesce(func.sum(UsageEvent.input_tokens + UsageEvent.output_tokens), 0)
    ).where(UsageEvent.workspace_id == workspace_id, UsageEvent.created_at >= since)
    return int((await db.execute(stmt)).scalar_one())


async def cost_since(db: AsyncSession, workspace_id: uuid.UUID, since: datetime) -> float | None:
    stmt = select(func.sum(UsageEvent.cost_usd)).where(
        UsageEvent.workspace_id == workspace_id, UsageEvent.created_at >= since
    )
    value = (await db.execute(stmt)).scalar_one()
    return float(value) if value is not None else None


async def usage_for_message(db: AsyncSession, message_id: uuid.UUID) -> list[UsageEvent]:
    stmt = select(UsageEvent).where(UsageEvent.message_id == message_id).order_by(UsageEvent.id)
    return list((await db.execute(stmt)).scalars())


async def upsert_feedback(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    rating: FeedbackRating,
    comment: str | None,
) -> None:
    stmt = insert(Feedback).values(
        id=uuid7(),
        workspace_id=workspace_id,
        message_id=message_id,
        user_id=user_id,
        rating=rating,
        comment=comment,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_feedback_message_id",
        set_={
            "rating": stmt.excluded.rating,
            "comment": stmt.excluded.comment,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)


async def delete_feedback(db: AsyncSession, *, message_id: uuid.UUID, user_id: uuid.UUID) -> None:
    feedback = (
        await db.execute(
            select(Feedback).where(Feedback.message_id == message_id, Feedback.user_id == user_id)
        )
    ).scalar_one_or_none()
    if feedback is not None:
        await db.delete(feedback)


async def list_unanswered(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    status: UnansweredStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[UnansweredQuestion], int]:
    where = [UnansweredQuestion.workspace_id == workspace_id]
    if status is not None:
        where.append(UnansweredQuestion.status == status)
    total = int(
        (
            await db.execute(select(func.count()).select_from(UnansweredQuestion).where(*where))
        ).scalar_one()
    )
    stmt = (
        select(UnansweredQuestion)
        .where(*where)
        .order_by(UnansweredQuestion.created_at.desc(), UnansweredQuestion.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list((await db.execute(stmt)).scalars()), total


async def get_unanswered(
    db: AsyncSession, workspace_id: uuid.UUID, item_id: uuid.UUID
) -> UnansweredQuestion | None:
    stmt = select(UnansweredQuestion).where(
        UnansweredQuestion.id == item_id, UnansweredQuestion.workspace_id == workspace_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def question_stats(db: AsyncSession, workspace_id: uuid.UUID) -> dict[str, int]:
    now = datetime.now(UTC)
    questions = select(
        func.count().filter(Message.created_at >= now - timedelta(days=7)),
        func.count().filter(Message.created_at >= now - timedelta(days=30)),
    ).where(Message.workspace_id == workspace_id, Message.role == MessageRole.user)
    last_7d, last_30d = (await db.execute(questions)).one()
    open_unanswered = (
        await db.execute(
            select(func.count()).where(
                UnansweredQuestion.workspace_id == workspace_id,
                UnansweredQuestion.status == UnansweredStatus.open,
            )
        )
    ).scalar_one()
    ratings = (
        select(
            func.count().filter(Feedback.rating == FeedbackRating.helpful),
            func.count(),
        )
        .select_from(Feedback)
        .where(Feedback.workspace_id == workspace_id)
    )
    helpful, rated = (await db.execute(ratings)).one()
    return {
        "last_7d": int(last_7d),
        "last_30d": int(last_30d),
        "unanswered_open": int(open_unanswered),
        "helpful": int(helpful),
        "rated": int(rated),
    }
