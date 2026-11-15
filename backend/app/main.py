"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import CsrfMiddleware, RequestIdMiddleware
from app.core.rate_limit import DisabledRateLimiter, InMemoryRateLimiter, RateLimiter
from app.db.session import create_engine, create_sessionmaker
from app.providers.storage import build_storage
from app.rag.factory import build_engine
from app.services.suggestions import default_cheap_llm


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "development")

    engine = create_engine(settings, null_pool=settings.environment == "test")
    # One pooled client for every AI provider call (embeddings, answers, suggestions).
    http = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await http.aclose()
        await engine.dispose()

    is_prod = settings.environment == "production"
    app = FastAPI(
        title=f"{settings.product_name} API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if is_prod else "/api/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/api/openapi.json",
    )
    limiter: RateLimiter = (
        InMemoryRateLimiter() if settings.rate_limit_enabled else DisabledRateLimiter()
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.limiter = limiter
    app.state.storage = build_storage(settings)
    app.state.http = http
    # Swappable in tests (fake providers with test thresholds); production uses the defaults.
    app.state.engine_factory = build_engine
    app.state.cheap_llm_factory = default_cheap_llm

    register_error_handlers(app)
    # Last added runs first: request ids are assigned before the CSRF check can reject.
    app.add_middleware(CsrfMiddleware, settings=settings)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(v1_router)
    return app
