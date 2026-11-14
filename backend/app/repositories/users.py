"""User, session and token persistence. These tables are identity data, not tenant data."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthSession, AuthToken, TokenPurpose, User


def utcnow() -> datetime:
    return datetime.now(UTC)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_session_by_hash(db: AsyncSession, token_hash: str) -> AuthSession | None:
    result = await db.execute(
        select(AuthSession).where(AuthSession.token_hash == token_hash).with_for_update()
    )
    return result.scalar_one_or_none()


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> AuthSession | None:
    return await db.get(AuthSession, session_id)


async def revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def revoke_all_sessions(
    db: AsyncSession, user_id: uuid.UUID, *, except_family: uuid.UUID | None = None
) -> None:
    stmt = update(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
    )
    if except_family is not None:
        stmt = stmt.where(AuthSession.family_id != except_family)
    await db.execute(stmt.values(revoked_at=utcnow()))


async def get_valid_token(
    db: AsyncSession, token_hash: str, purpose: TokenPurpose
) -> AuthToken | None:
    result = await db.execute(
        select(AuthToken)
        .where(
            AuthToken.token_hash == token_hash,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > utcnow(),
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def invalidate_tokens(db: AsyncSession, user_id: uuid.UUID, purpose: TokenPurpose) -> None:
    await db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
