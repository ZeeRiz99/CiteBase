"""Workspace settings, team members, invitations, and the public invite-acceptance endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.cookies import set_auth_cookies
from app.api.deps import (
    AuthServiceDep,
    ClientDep,
    CurrentContext,
    DbDep,
    SettingsDep,
    get_limiter,
    require_role,
)
from app.models import Role
from app.repositories import system as system_repo
from app.schemas.auth import MessageResponse
from app.schemas.team import (
    AcceptInvitationRequest,
    InvitationOut,
    InvitationPreviewOut,
    InvitationTokenRequest,
    InviteRequest,
    MemberOut,
    RoleUpdate,
    WorkspaceSettingsOut,
    WorkspaceUpdate,
)
from app.services.team import TeamService

router = APIRouter(tags=["team"])

Viewer = Annotated[CurrentContext, Depends(require_role(Role.viewer))]
Admin = Annotated[CurrentContext, Depends(require_role(Role.admin))]
VerifiedAdmin = Annotated[CurrentContext, Depends(require_role(Role.admin, verified=True))]


def _team(request: Request, db: DbDep, settings: SettingsDep, ctx: CurrentContext) -> TeamService:
    return TeamService(db, settings, get_limiter(request), ctx)


# ---- workspace ----------------------------------------------------------------------------


def _workspace_out(ctx: CurrentContext, settings: SettingsDep) -> WorkspaceSettingsOut:
    own = ctx.workspace.monthly_token_limit
    limit = own if own is not None else settings.monthly_token_limit
    return WorkspaceSettingsOut(
        id=ctx.workspace.id,
        name=ctx.workspace.name,
        slug=ctx.workspace.slug,
        monthly_token_limit=limit or None,
        token_limit_source="workspace" if own is not None else "default",
    )


@router.get("/workspace")
async def get_workspace(ctx: Viewer, settings: SettingsDep) -> WorkspaceSettingsOut:
    return _workspace_out(ctx, settings)


@router.patch("/workspace")
async def update_workspace(
    body: WorkspaceUpdate, ctx: Admin, db: DbDep, settings: SettingsDep
) -> WorkspaceSettingsOut:
    ctx.workspace.name = body.name
    system_repo.add_audit(
        db, action="workspace.renamed", workspace_id=ctx.workspace.id, actor_user_id=ctx.user.id
    )
    await db.commit()
    return _workspace_out(ctx, settings)


# ---- members ------------------------------------------------------------------------------


@router.get("/workspace/members")
async def list_members(
    request: Request, ctx: Admin, db: DbDep, settings: SettingsDep
) -> list[MemberOut]:
    members = await _team(request, db, settings, ctx).members()
    return [MemberOut.build(m, ctx.user.id) for m in members]


@router.patch("/workspace/members/{user_id}")
async def change_member_role(
    user_id: uuid.UUID,
    body: RoleUpdate,
    request: Request,
    ctx: Admin,
    db: DbDep,
    settings: SettingsDep,
) -> MessageResponse:
    await _team(request, db, settings, ctx).change_role(user_id, Role(body.role))
    return MessageResponse(message="Role updated.")


@router.delete("/workspace/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID, request: Request, ctx: Admin, db: DbDep, settings: SettingsDep
) -> Response:
    await _team(request, db, settings, ctx).remove(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- invitations --------------------------------------------------------------------------


@router.get("/workspace/invitations")
async def list_invitations(
    request: Request, ctx: Admin, db: DbDep, settings: SettingsDep
) -> list[InvitationOut]:
    items = await _team(request, db, settings, ctx).pending_invitations()
    return [InvitationOut.build(i) for i in items]


@router.post("/workspace/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InviteRequest, request: Request, ctx: VerifiedAdmin, db: DbDep, settings: SettingsDep
) -> InvitationOut:
    created = await _team(request, db, settings, ctx).invite(str(body.email), Role(body.role))
    return InvitationOut.build(created.invitation, created.link)


@router.delete("/workspace/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: uuid.UUID, request: Request, ctx: Admin, db: DbDep, settings: SettingsDep
) -> Response:
    await _team(request, db, settings, ctx).revoke(invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Public: the invite link. Tokens travel in the body, never in a URL that could be logged.


@router.post("/invitations/preview")
async def preview_invitation(
    body: InvitationTokenRequest, service: AuthServiceDep, client: ClientDep
) -> InvitationPreviewOut:
    return InvitationPreviewOut.build(
        await service.preview_invitation(token=body.token, client=client)
    )


@router.post("/invitations/accept")
async def accept_invitation(
    body: AcceptInvitationRequest,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    client: ClientDep,
) -> MessageResponse:
    tokens = await service.accept_invitation(
        token=body.token, full_name=body.full_name, password=body.password, client=client
    )
    set_auth_cookies(response, settings, tokens)
    return MessageResponse(message="Welcome aboard.")
