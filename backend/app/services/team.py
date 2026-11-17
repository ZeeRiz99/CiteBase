"""Team management: members, roles and invitations.

Rules: only admins and the owner manage the team; an actor can only manage people whose role is
below their own and can only grant roles below their own (so admins manage members and viewers,
the owner also manages admins). The owner cannot be changed or removed here. Invited people get a
new account in this workspace; an email that already has an account cannot be invited (one
workspace per account until multi-workspace support lands).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentContext
from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.rate_limit import RateLimiter, enforce
from app.core.security import new_opaque_token
from app.db.ids import uuid7
from app.models import ROLE_RANK, Invitation, Membership, Role, User
from app.repositories import system as system_repo
from app.repositories import users as users_repo
from app.services import emails


@dataclass(frozen=True)
class Member:
    user_id: uuid.UUID
    full_name: str
    email: str
    role: Role
    joined_at: datetime


@dataclass(frozen=True)
class CreatedInvitation:
    invitation: Invitation
    link: str  # shown once to the inviting admin; only the hash is stored


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_pending(invitation: Invitation, now: datetime) -> bool:
    return (
        invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > now
    )


class TeamService:
    def __init__(
        self, db: AsyncSession, settings: Settings, limiter: RateLimiter, ctx: CurrentContext
    ) -> None:
        self.db = db
        self.settings = settings
        self.limiter = limiter
        self.ctx = ctx

    @property
    def _rank(self) -> int:
        return ROLE_RANK[self.ctx.role]

    def _check_grantable(self, role: Role) -> None:
        if role == Role.owner or ROLE_RANK[role] >= self._rank:
            raise Forbidden("You can only give roles below your own.")

    # ---- members --------------------------------------------------------------------------

    async def members(self) -> list[Member]:
        rows = await self.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.workspace_id == self.ctx.workspace.id, User.deleted_at.is_(None))
            .order_by(Membership.created_at)
        )
        return [Member(u.id, u.full_name, u.email, m.role, m.created_at) for m, u in rows.all()]

    async def _manageable(self, user_id: uuid.UUID) -> Membership:
        result = await self.db.execute(
            select(Membership).where(
                Membership.workspace_id == self.ctx.workspace.id, Membership.user_id == user_id
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise NotFound()
        if user_id == self.ctx.user.id or ROLE_RANK[membership.role] >= self._rank:
            raise Forbidden("You can only manage people whose role is below your own.")
        return membership

    async def change_role(self, user_id: uuid.UUID, role: Role) -> Membership:
        membership = await self._manageable(user_id)
        self._check_grantable(role)
        previous = membership.role
        membership.role = role
        system_repo.add_audit(
            self.db,
            action="team.role_changed",
            workspace_id=self.ctx.workspace.id,
            actor_user_id=self.ctx.user.id,
            target_type="user",
            target_id=str(user_id),
            details={"from": previous.value, "to": role.value},
        )
        await self.db.commit()
        return membership

    async def remove(self, user_id: uuid.UUID) -> None:
        membership = await self._manageable(user_id)
        await self.db.delete(membership)
        # Their account only belonged to this workspace: end every session right away.
        await users_repo.revoke_all_sessions(self.db, user_id)
        system_repo.add_audit(
            self.db,
            action="team.member_removed",
            workspace_id=self.ctx.workspace.id,
            actor_user_id=self.ctx.user.id,
            target_type="user",
            target_id=str(user_id),
        )
        await self.db.commit()

    # ---- invitations ----------------------------------------------------------------------

    async def pending_invitations(self) -> list[Invitation]:
        result = await self.db.execute(
            select(Invitation)
            .where(
                Invitation.workspace_id == self.ctx.workspace.id,
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.expires_at > users_repo.utcnow(),
            )
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars())

    async def invite(self, email: str, role: Role) -> CreatedInvitation:
        await enforce(self.limiter, f"invite:user:{self.ctx.user.id}", 30, 3600)
        self._check_grantable(role)
        email = normalize_email(email)
        if await users_repo.get_user_by_email(self.db, email):
            raise Conflict(
                "This person already has an account, so they cannot be invited yet.",
                code="email_taken",
            )
        now = users_repo.utcnow()
        # Inviting the same address again replaces the earlier link (acts as "resend").
        for old in await self.pending_invitations():
            if old.email.lower() == email:
                old.revoked_at = now
        raw, token_hash = new_opaque_token()
        invitation = Invitation(
            id=uuid7(),
            workspace_id=self.ctx.workspace.id,
            email=email,
            role=role,
            token_hash=token_hash,
            invited_by_id=self.ctx.user.id,
            expires_at=now + timedelta(days=self.settings.invitation_ttl_days),
        )
        self.db.add(invitation)
        link = f"{self.settings.app_base_url.rstrip('/')}/invite?{urlencode({'token': raw})}"
        system_repo.enqueue_job(
            self.db,
            job_type="send_email",
            payload={
                "template": emails.INVITATION,
                "context": {
                    "to": email,
                    "link": link,
                    "inviter": self.ctx.user.full_name,
                    "workspace": self.ctx.workspace.name,
                },
            },
        )
        system_repo.add_audit(
            self.db,
            action="team.invited",
            workspace_id=self.ctx.workspace.id,
            actor_user_id=self.ctx.user.id,
            target_type="invitation",
            target_id=str(invitation.id),
            details={"role": role.value},
        )
        await self.db.commit()
        return CreatedInvitation(invitation, link)

    async def revoke(self, invitation_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Invitation).where(
                Invitation.id == invitation_id, Invitation.workspace_id == self.ctx.workspace.id
            )
        )
        invitation = result.scalar_one_or_none()
        if invitation is None or not is_pending(invitation, users_repo.utcnow()):
            raise NotFound()
        if ROLE_RANK[invitation.role] >= self._rank:
            raise Forbidden("You can only manage invitations for roles below your own.")
        invitation.revoked_at = users_repo.utcnow()
        system_repo.add_audit(
            self.db,
            action="team.invitation_revoked",
            workspace_id=self.ctx.workspace.id,
            actor_user_id=self.ctx.user.id,
            target_type="invitation",
            target_id=str(invitation.id),
        )
        await self.db.commit()
