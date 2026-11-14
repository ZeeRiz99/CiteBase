"""Database engine, sessions and the tenant (RLS) context.

Tenant context is stored in `session.info` and applied with `set_config(..., is_local => true)`
at the start of every transaction, so it survives commits within a request and can never leak
to another request through the connection pool (SET LOCAL ends with the transaction).
"""

from __future__ import annotations

import uuid

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.pool import NullPool

from app.core.config import Settings

_WS_KEY = "tenant_workspace_id"
_USER_KEY = "tenant_user_id"
_SET_CONTEXT_SQL = text(
    "SELECT set_config('app.workspace_id', :wid, true), set_config('app.user_id', :uid, true)"
)


def create_engine(settings: Settings, *, null_pool: bool = False) -> AsyncEngine:
    if null_pool:
        return create_async_engine(settings.database_url, poolclass=NullPool)
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_size,
        pool_pre_ping=True,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _context_params(session: Session) -> dict[str, str]:
    wid = session.info.get(_WS_KEY)
    uid = session.info.get(_USER_KEY)
    return {"wid": str(wid) if wid else "", "uid": str(uid) if uid else ""}


@event.listens_for(Session, "after_begin")
def _apply_tenant_context(
    session: Session, _transaction: SessionTransaction, connection: Connection
) -> None:
    connection.execute(_SET_CONTEXT_SQL, _context_params(session))


async def set_tenant(
    session: AsyncSession, *, workspace_id: uuid.UUID | None, user_id: uuid.UUID | None
) -> None:
    """Set who the current transaction acts for. Rows of other workspaces become invisible."""
    session.info[_WS_KEY] = workspace_id
    session.info[_USER_KEY] = user_id
    if session.in_transaction():
        await session.execute(_SET_CONTEXT_SQL, _context_params(session.sync_session))
