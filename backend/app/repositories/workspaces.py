"""Workspace and membership queries. Visibility is enforced twice: explicit filters here and RLS."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Collection, Membership, Workspace


async def get_membership(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> Membership | None:
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def first_membership(db: AsyncSession, user_id: uuid.UUID) -> Membership | None:
    result = await db.execute(
        select(Membership)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user_id, Workspace.deleted_at.is_(None))
        .order_by(Membership.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def list_collections(db: AsyncSession, workspace_id: uuid.UUID) -> list[Collection]:
    result = await db.execute(
        select(Collection)
        .where(Collection.workspace_id == workspace_id, Collection.deleted_at.is_(None))
        .order_by(Collection.created_at)
    )
    return list(result.scalars())
