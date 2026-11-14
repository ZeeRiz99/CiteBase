"""Request dependencies: database session, settings, current user/workspace and role checks.

Workspace and role always come from the server-side session, never from client input.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import ACCESS_COOKIE
from app.core.config import Settings
from app.core.errors import Forbidden, NotAuthenticated
from app.core.rate_limit import RateLimiter
from app.core.security import decode_access_token
from app.db.session import set_tenant
from app.models import ROLE_RANK, Role, User, Workspace
from app.repositories import users as users_repo
from app.repositories import workspaces as ws_repo
from app.services.auth import AuthService, ClientInfo


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    # The session is opened and closed in this one generator, so an exception raised by the
    # endpoint closes it (rolling back and releasing locks) instead of waiting for GC.
    async with request.app.state.sessionmaker() as session:
        yield session


def get_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.limiter
    return limiter


def get_client_info(request: Request) -> ClientInfo:
    return ClientInfo(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
ClientDep = Annotated[ClientInfo, Depends(get_client_info)]


def get_auth_service(db: DbDep, settings: SettingsDep, request: Request) -> AuthService:
    return AuthService(db, settings, get_limiter(request))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@dataclass(frozen=True)
class CurrentContext:
    user: User
    workspace: Workspace
    role: Role
    session_id: uuid.UUID
    family_id: uuid.UUID


async def get_current(request: Request, db: DbDep, settings: SettingsDep) -> CurrentContext:
    token = request.cookies.get(ACCESS_COOKIE)
    claims = decode_access_token(settings, token) if token else None
    if claims is None:
        raise NotAuthenticated()

    await set_tenant(db, workspace_id=claims.workspace_id, user_id=claims.user_id)
    session = await users_repo.get_session(db, claims.session_id)
    if session is None or session.revoked_at is not None or session.user_id != claims.user_id:
        raise NotAuthenticated()
    user = await users_repo.get_user(db, claims.user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated()
    membership = await ws_repo.get_membership(
        db, workspace_id=claims.workspace_id, user_id=claims.user_id
    )
    workspace = await ws_repo.get_workspace(db, claims.workspace_id)
    if membership is None or workspace is None:
        raise NotAuthenticated()
    return CurrentContext(
        user=user,
        workspace=workspace,
        role=membership.role,
        session_id=session.id,
        family_id=session.family_id,
    )


CurrentDep = Annotated[CurrentContext, Depends(get_current)]


def require_role(minimum: Role) -> Callable[[CurrentContext], Awaitable[CurrentContext]]:
    async def _check(ctx: CurrentDep) -> CurrentContext:
        if ROLE_RANK[ctx.role] < ROLE_RANK[minimum]:
            raise Forbidden()
        return ctx

    return _check
