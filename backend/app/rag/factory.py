"""Build a RagEngine for a workspace from settings (used by the CLI, evals and, later, chat)."""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Workspace
from app.providers.embeddings import EmbeddingProvider, build_embedder
from app.providers.llm import LLMProvider, build_llm
from app.rag.engine import EngineConfig, RagEngine, engine_config_from
from app.rag.profiles import get_profile


def build_engine(
    db: AsyncSession,
    settings: Settings,
    workspace: Workspace,
    http: httpx.AsyncClient,
    *,
    config: EngineConfig | None = None,
    embedder: EmbeddingProvider | None = None,
    llm: LLMProvider | None = None,
    cheap_llm: LLMProvider | None = None,
) -> RagEngine:
    profile = get_profile(workspace.embedding_profile_id)
    return RagEngine(
        db=db,
        workspace_id=workspace.id,
        fts_config=workspace.fts_config,
        profile=profile,
        embedder=embedder or build_embedder(settings, profile.id, http),
        llm=llm or build_llm(settings, http),
        cheap_llm=cheap_llm or build_llm(settings, http, model=settings.llm_cheap_model),
        config=config or engine_config_from(settings),
    )
