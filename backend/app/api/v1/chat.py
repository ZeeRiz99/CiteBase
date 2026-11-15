from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import CurrentContext, DbDep, SettingsDep, require_role
from app.api.sse import EventStreamResponse
from app.core.errors import NotFound
from app.models import MessageRole, Role, UnansweredStatus
from app.repositories import chat as chat_repo
from app.schemas.auth import MessageResponse
from app.schemas.chat import (
    AskRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationPatch,
    FeedbackRequest,
    SuggestedQuestions,
    TraceOut,
    UnansweredList,
    UnansweredOut,
    UnansweredPatch,
    UsageOut,
)
from app.services.chat import Actor, ChatService
from app.services.suggestions import suggested_questions

router = APIRouter(tags=["chat"])

Viewer = Annotated[CurrentContext, Depends(require_role(Role.viewer))]
Member = Annotated[CurrentContext, Depends(require_role(Role.member))]
Admin = Annotated[CurrentContext, Depends(require_role(Role.admin))]


def _chat(request: Request, db: DbDep, settings: SettingsDep, ctx: CurrentContext) -> ChatService:
    return ChatService(
        db,
        settings,
        Actor(user_id=ctx.user.id, workspace=ctx.workspace),
        http=request.app.state.http,
        limiter=request.app.state.limiter,
        engine_factory=request.app.state.engine_factory,
    )


@router.get("/conversations")
async def list_conversations(
    request: Request,
    ctx: Viewer,
    db: DbDep,
    settings: SettingsDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> list[ConversationOut]:
    rows = await _chat(request, db, settings, ctx).list_conversations(q.strip() if q else None)
    return [ConversationOut.build(c) for c in rows]


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: Request, body: ConversationCreate, ctx: Member, db: DbDep, settings: SettingsDep
) -> ConversationOut:
    conversation = await _chat(request, db, settings, ctx).create_conversation(body.title)
    return ConversationOut.build(conversation)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    request: Request, conversation_id: uuid.UUID, ctx: Viewer, db: DbDep, settings: SettingsDep
) -> ConversationDetail:
    conversation, messages = await _chat(request, db, settings, ctx).thread(conversation_id)
    return ConversationDetail(**ConversationOut.build(conversation).model_dump(), messages=messages)


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    body: ConversationPatch,
    ctx: Viewer,
    db: DbDep,
    settings: SettingsDep,
) -> ConversationOut:
    conversation = await _chat(request, db, settings, ctx).rename(conversation_id, body.title)
    return ConversationOut.build(conversation)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    request: Request, conversation_id: uuid.UUID, ctx: Viewer, db: DbDep, settings: SettingsDep
) -> MessageResponse:
    await _chat(request, db, settings, ctx).delete(conversation_id)
    return MessageResponse(message="Conversation deleted.")


@router.post("/conversations/{conversation_id}/messages", response_class=EventStreamResponse)
async def ask(
    request: Request,
    conversation_id: uuid.UUID,
    body: AskRequest,
    ctx: Member,
    db: DbDep,
    settings: SettingsDep,
) -> EventStreamResponse:
    """Server-Sent Events: meta, token*, replace?, (citations | refusal | error), done."""
    service = _chat(request, db, settings, ctx)
    turn = await service.prepare_ask(conversation_id, body.question)
    return EventStreamResponse(service.stream(turn))


@router.post("/messages/{message_id}/regenerate", response_class=EventStreamResponse)
async def regenerate(
    request: Request, message_id: uuid.UUID, ctx: Member, db: DbDep, settings: SettingsDep
) -> EventStreamResponse:
    service = _chat(request, db, settings, ctx)
    turn = await service.prepare_regenerate(message_id)
    return EventStreamResponse(service.stream(turn))


@router.post("/messages/{message_id}/feedback")
async def give_feedback(
    request: Request,
    message_id: uuid.UUID,
    body: FeedbackRequest,
    ctx: Member,
    db: DbDep,
    settings: SettingsDep,
) -> MessageResponse:
    await _chat(request, db, settings, ctx).set_feedback(message_id, body.rating, body.comment)
    return MessageResponse(message="Thanks for the feedback.")


@router.delete("/messages/{message_id}/feedback")
async def clear_feedback(
    request: Request, message_id: uuid.UUID, ctx: Member, db: DbDep, settings: SettingsDep
) -> MessageResponse:
    await _chat(request, db, settings, ctx).clear_feedback(message_id)
    return MessageResponse(message="Feedback removed.")


@router.get("/messages/{message_id}/trace")
async def message_trace(message_id: uuid.UUID, ctx: Admin, db: DbDep) -> TraceOut:
    """The admin "why this answer?" view: retrieval, gate signals vs thresholds, tokens, cost."""
    message = await chat_repo.get_message(db, ctx.workspace.id, message_id)
    if message is None or message.role != MessageRole.assistant:
        raise NotFound()
    question = await chat_repo.previous_user_message(db, message)
    usage = await chat_repo.usage_for_message(db, message.id)
    costs = [float(u.cost_usd) for u in usage if u.cost_usd is not None]
    return TraceOut(
        message_id=message.id,
        question=question.content if question else None,
        standalone_query=message.standalone_query,
        status=message.status,
        evidence=message.evidence_strength,
        refusal_reason=message.refusal_reason,
        prompt_version=message.prompt_version,
        llm_provider=message.llm_provider,
        llm_model=message.llm_model,
        input_tokens=message.input_tokens,
        output_tokens=message.output_tokens,
        latency_ms=message.latency_ms,
        cost_usd=round(sum(costs), 6) if costs else None,
        trace=message.retrieval_trace or {},
    )


@router.get("/suggested-questions")
async def get_suggested_questions(
    request: Request, ctx: Viewer, db: DbDep, settings: SettingsDep
) -> SuggestedQuestions:
    questions = await suggested_questions(
        db,
        settings,
        ctx.workspace,
        ctx.user.id,
        request.app.state.http,
        request.app.state.cheap_llm_factory,
    )
    return SuggestedQuestions(questions=questions)


@router.get("/unanswered-questions")
async def list_unanswered(
    ctx: Admin,
    db: DbDep,
    status_filter: Annotated[UnansweredStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> UnansweredList:
    items, total = await chat_repo.list_unanswered(
        db, ctx.workspace.id, status=status_filter, page=page, page_size=page_size
    )
    return UnansweredList(
        items=[UnansweredOut.build(u) for u in items], total=total, page=page, page_size=page_size
    )


@router.patch("/unanswered-questions/{item_id}")
async def update_unanswered(
    item_id: uuid.UUID, body: UnansweredPatch, ctx: Admin, db: DbDep
) -> UnansweredOut:
    item = await chat_repo.get_unanswered(db, ctx.workspace.id, item_id)
    if item is None:
        raise NotFound()
    item.status = body.status
    await db.commit()
    return UnansweredOut.build(item)


@router.get("/workspace/usage")
async def workspace_usage(
    request: Request, ctx: Admin, db: DbDep, settings: SettingsDep
) -> UsageOut:
    service = _chat(request, db, settings, ctx)
    since = chat_repo.month_start()
    return UsageOut(
        period_start=since,
        tokens_used=await chat_repo.tokens_since(db, ctx.workspace.id, since),
        token_limit=service.token_limit(),
        cost_usd=await chat_repo.cost_since(db, ctx.workspace.id, since),
    )
