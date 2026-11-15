"""Suggested starter questions, written by the cheap model from the workspace's own passages.

Each question is generated from one real passage, so it is answerable by construction. The list
is cached in `workspaces.settings` under a key derived from the set of indexed versions, so it
is regenerated only when documents change. Failures return an empty list (never cached).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from decimal import Decimal

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.pricing import cost_usd
from app.models import Chunk, Document, UsageEvent, UsageKind, Workspace
from app.providers.http import ProviderError, ProviderNotConfigured
from app.providers.llm import GenerationParams, LLMMessage, LLMProvider, build_llm, complete

log = structlog.get_logger("suggestions")

LLMFactory = Callable[[Settings, httpx.AsyncClient], LLMProvider]
MAX_DOCUMENTS = 6
MAX_QUESTIONS = 4
PASSAGE_CHARS = 1200
CACHE_FIELD = "suggested_questions"

SYSTEM = (
    "You write starter questions for a company knowledge base. For each passage, write one "
    "short, natural question (at most 14 words) that a colleague might ask and that the passage "
    "answers directly. Use the passage's language. Do not mention 'the passage' or 'the "
    'document\'. Reply as JSON: {"questions": ["..."]}.'
)


def default_cheap_llm(settings: Settings, http: httpx.AsyncClient) -> LLMProvider:
    return build_llm(settings, http, model=settings.llm_cheap_model)


async def _passages(db: AsyncSession, workspace_id: uuid.UUID) -> list[tuple[str, str]]:
    """(version id, passage) for the most recent indexed documents: their richest early chunk."""
    docs = (
        await db.execute(
            select(Document.title, Document.current_version_id)
            .where(
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                Document.current_version_id.is_not(None),
            )
            .order_by(Document.updated_at.desc())
            .limit(MAX_DOCUMENTS)
        )
    ).all()
    out: list[tuple[str, str]] = []
    for title, version_id in docs:
        chunks = (
            await db.execute(
                select(Chunk.text)
                .where(Chunk.document_version_id == version_id, Chunk.chunk_index < 3)
                .order_by(Chunk.token_count.desc())
                .limit(1)
            )
        ).scalars()
        best = next(iter(chunks), None)
        if best:
            out.append((str(version_id), f"{title}\n{best[:PASSAGE_CHARS]}"))
    return out


def _parse(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    items = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    seen: set[str] = set()
    questions: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        q = " ".join(item.split()).rstrip("?").strip()
        if 8 <= len(q) <= 160 and q.lower() not in seen:
            seen.add(q.lower())
            questions.append(q + "?")
    return questions[:MAX_QUESTIONS]


async def suggested_questions(
    db: AsyncSession,
    settings: Settings,
    workspace: Workspace,
    user_id: uuid.UUID,
    http: httpx.AsyncClient,
    llm_factory: LLMFactory = default_cheap_llm,
) -> list[str]:
    passages = await _passages(db, workspace.id)
    if not passages:
        return []
    key = hashlib.sha256(",".join(sorted(v for v, _ in passages)).encode()).hexdigest()[:32]
    cached = (workspace.settings or {}).get(CACHE_FIELD)
    if isinstance(cached, dict) and cached.get("key") == key:
        return [str(q) for q in cached.get("questions", [])]

    try:
        llm = llm_factory(settings, http)
        body = "\n\n".join(f"<passage>\n{p}\n</passage>" for _, p in passages)
        result = await complete(
            llm,
            SYSTEM,
            [LLMMessage("user", body)],
            GenerationParams(temperature=0.3, max_tokens=400, json_output=True),
        )
    except (ProviderError, ProviderNotConfigured) as exc:
        log.warning("suggestions_unavailable", error=str(exc))
        return []
    questions = _parse(result.text)

    cost = cost_usd(result.usage.model, result.usage.input_tokens, result.usage.output_tokens)
    db.add(
        UsageEvent(
            workspace_id=workspace.id,
            user_id=user_id,
            kind=UsageKind.suggest,
            provider=getattr(llm, "name", "unknown"),
            model=result.usage.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=Decimal(str(round(cost, 6))) if cost is not None else None,
        )
    )
    if questions:
        # jsonb_set keeps any other workspace settings written concurrently.
        await db.execute(
            text(
                "UPDATE workspaces SET settings = jsonb_set(settings, CAST(:path AS text[]), "
                "CAST(:value AS jsonb)) WHERE id = :id"
            ),
            {
                "path": "{" + CACHE_FIELD + "}",
                "value": json.dumps({"key": key, "questions": questions}),
                "id": workspace.id,
            },
        )
    await db.commit()
    return questions
