from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

from app.models import Invitation
from app.schemas.auth import Name, Password, Token, _Strict
from app.services.auth import InvitationPreview
from app.services.team import Member

GrantableRole = Literal["admin", "member", "viewer"]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    joined_at: datetime
    is_you: bool

    @classmethod
    def build(cls, m: Member, me: uuid.UUID) -> MemberOut:
        return cls(
            user_id=m.user_id,
            full_name=m.full_name,
            email=m.email,
            role=m.role.value,
            joined_at=m.joined_at,
            is_you=m.user_id == me,
        )


class RoleUpdate(_Strict):
    role: GrantableRole


class InviteRequest(_Strict):
    email: EmailStr
    role: GrantableRole = "member"


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime
    expires_at: datetime
    link: str | None = None  # only in the response that creates the invitation

    @classmethod
    def build(cls, inv: Invitation, link: str | None = None) -> InvitationOut:
        return cls(
            id=inv.id,
            email=inv.email,
            role=inv.role.value,
            created_at=inv.created_at,
            expires_at=inv.expires_at,
            link=link,
        )


class InvitationPreviewOut(BaseModel):
    email: str
    role: str
    workspace_name: str
    inviter_name: str | None
    expires_at: datetime

    @classmethod
    def build(cls, p: InvitationPreview) -> InvitationPreviewOut:
        return cls(
            email=p.email,
            role=p.role.value,
            workspace_name=p.workspace_name,
            inviter_name=p.inviter_name,
            expires_at=p.expires_at,
        )


class InvitationTokenRequest(_Strict):
    token: Token


class AcceptInvitationRequest(_Strict):
    token: Token
    full_name: Name
    password: Password


class WorkspaceSettingsOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    monthly_token_limit: int | None  # effective allowance; None = unlimited
    token_limit_source: Literal["workspace", "default"]


class WorkspaceUpdate(_Strict):
    name: Name
