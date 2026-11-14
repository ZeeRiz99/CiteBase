"""Authentication use cases: register, login, refresh, logout, email verification, password reset.

Route handlers stay thin; everything that touches tokens, sessions or audit lives here.
"""

from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, Conflict, InvalidCredentials, NotAuthenticated
from app.core.rate_limit import RateLimiter, enforce
from app.core.security import (
    AccessClaims,
    create_access_token,
    hash_ip,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from app.db.ids import uuid7
from app.db.session import set_tenant
from app.models import (
    AuthSession,
    AuthToken,
    Collection,
    Membership,
    Role,
    TokenPurpose,
    User,
    Workspace,
)
from app.repositories import system as system_repo
from app.repositories import users as users_repo
from app.repositories import workspaces as ws_repo
from app.services import emails

# A second refresh with an already-rotated token inside this window is treated as a benign
# race between browser tabs (cookies are shared, so the other request already has new ones).
REFRESH_RACE_GRACE = timedelta(seconds=20)


class InvalidToken(AppError):
    status_code = 400
    code = "invalid_token"
    message = "This link is invalid or has expired. Request a new one."


class WrongPassword(AppError):
    status_code = 400
    code = "wrong_password"
    message = "Your current password is incorrect."


@dataclass(frozen=True)
class ClientInfo:
    ip: str | None
    user_agent: str | None


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    session: AuthSession


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "workspace"
    return f"{base}-{secrets.token_hex(3)}"


class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self.db = db
        self.settings = settings
        self.limiter = limiter

    # ---- helpers -------------------------------------------------------------------------

    def _issue_tokens(
        self,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        client: ClientInfo,
        family_id: uuid.UUID | None = None,
    ) -> IssuedTokens:
        raw, token_hash = new_opaque_token()
        session = AuthSession(
            id=uuid7(),
            user_id=user_id,
            workspace_id=workspace_id,
            family_id=family_id or uuid7(),
            token_hash=token_hash,
            expires_at=users_repo.utcnow() + timedelta(days=self.settings.refresh_token_ttl_days),
            user_agent=(client.user_agent or "")[:300] or None,
            ip_hash=hash_ip(self.settings, client.ip),
        )
        self.db.add(session)
        access = create_access_token(
            self.settings,
            AccessClaims(user_id=user_id, workspace_id=workspace_id, session_id=session.id),
        )
        return IssuedTokens(access_token=access, refresh_token=raw, session=session)

    def _link(self, path: str, token: str) -> str:
        return f"{self.settings.app_base_url.rstrip('/')}{path}?{urlencode({'token': token})}"

    def _queue_token_email(
        self, user: User, purpose: TokenPurpose, ttl: timedelta, template: str, path: str
    ) -> None:
        raw, token_hash = new_opaque_token()
        self.db.add(
            AuthToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=token_hash,
                expires_at=users_repo.utcnow() + ttl,
            )
        )
        system_repo.enqueue_job(
            self.db,
            job_type="send_email",
            payload={
                "template": template,
                "context": {
                    "to": user.email,
                    "name": user.full_name,
                    "link": self._link(path, raw),
                },
            },
        )

    def _queue_verification(self, user: User) -> None:
        self._queue_token_email(
            user,
            TokenPurpose.verify_email,
            timedelta(hours=self.settings.email_verification_ttl_hours),
            emails.VERIFY_EMAIL,
            "/verify-email",
        )

    # ---- use cases -----------------------------------------------------------------------

    async def register(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
        workspace_name: str | None,
        client: ClientInfo,
    ) -> IssuedTokens:
        await enforce(self.limiter, f"register:ip:{client.ip}", 5, 3600)
        email = normalize_email(email)
        if await users_repo.get_user_by_email(self.db, email):
            raise Conflict("An account with this email already exists.", code="email_taken")

        user_id, workspace_id = uuid7(), uuid7()
        await set_tenant(self.db, workspace_id=workspace_id, user_id=user_id)
        user = User(
            id=user_id, email=email, password_hash=hash_password(password), full_name=full_name
        )
        self.db.add(user)
        await self.db.flush()
        ws_name = workspace_name or f"{full_name.split(' ', maxsplit=1)[0]}'s workspace"
        self.db.add(Workspace(id=workspace_id, name=ws_name, slug=_slugify(ws_name)))
        await self.db.flush()
        self.db.add(Membership(workspace_id=workspace_id, user_id=user_id, role=Role.owner))
        self.db.add(Collection(workspace_id=workspace_id, name="General", is_default=True))
        self._queue_verification(user)
        system_repo.add_audit(
            self.db,
            action="auth.register",
            workspace_id=workspace_id,
            actor_user_id=user_id,
            ip_hash=hash_ip(self.settings, client.ip),
        )
        tokens = self._issue_tokens(user_id, workspace_id, client)
        try:
            await self.db.commit()
        except IntegrityError as exc:  # concurrent registration with the same email
            await self.db.rollback()
            raise Conflict(
                "An account with this email already exists.", code="email_taken"
            ) from exc
        return tokens

    async def login(self, *, email: str, password: str, client: ClientInfo) -> IssuedTokens:
        email = normalize_email(email)
        await enforce(self.limiter, f"login:ip:{client.ip}", 20, 300)
        await enforce(self.limiter, f"login:email:{email}", 10, 900)

        user = await users_repo.get_user_by_email(self.db, email)
        check = verify_password(password, user.password_hash if user else None)
        if user is None or not check.valid or not user.is_active:
            system_repo.add_audit(
                self.db,
                action="auth.login_failed",
                actor_user_id=user.id if user else None,
                ip_hash=hash_ip(self.settings, client.ip),
            )
            await self.db.commit()
            raise InvalidCredentials()

        if check.needs_rehash:
            user.password_hash = hash_password(password)
        await set_tenant(self.db, workspace_id=None, user_id=user.id)
        membership = await ws_repo.first_membership(self.db, user.id)
        if membership is None:
            raise InvalidCredentials()
        await set_tenant(self.db, workspace_id=membership.workspace_id, user_id=user.id)
        user.last_login_at = users_repo.utcnow()
        tokens = self._issue_tokens(user.id, membership.workspace_id, client)
        system_repo.add_audit(
            self.db,
            action="auth.login",
            workspace_id=membership.workspace_id,
            actor_user_id=user.id,
            ip_hash=hash_ip(self.settings, client.ip),
        )
        await self.db.commit()
        return tokens

    async def refresh(self, *, refresh_token: str | None, client: ClientInfo) -> IssuedTokens:
        if not refresh_token:
            raise NotAuthenticated()
        session = await users_repo.get_session_by_hash(self.db, hash_token(refresh_token))
        if session is None or session.revoked_at is not None:
            raise NotAuthenticated()

        now = users_repo.utcnow()
        if session.replaced_by_id is not None:
            if session.rotated_at and now - session.rotated_at <= REFRESH_RACE_GRACE:
                raise NotAuthenticated("Session was just refreshed.", code="refresh_race")
            # An old refresh token came back after rotation: assume theft, end the whole family.
            await users_repo.revoke_family(self.db, session.family_id)
            system_repo.add_audit(
                self.db,
                action="auth.refresh_reuse_detected",
                workspace_id=None,
                actor_user_id=session.user_id,
                ip_hash=hash_ip(self.settings, client.ip),
            )
            await self.db.commit()
            raise NotAuthenticated()
        if session.expires_at <= now:
            raise NotAuthenticated()

        user = await users_repo.get_user(self.db, session.user_id)
        await set_tenant(self.db, workspace_id=session.workspace_id, user_id=session.user_id)
        membership = await ws_repo.get_membership(
            self.db, workspace_id=session.workspace_id, user_id=session.user_id
        )
        if user is None or not user.is_active or membership is None:
            await users_repo.revoke_family(self.db, session.family_id)
            await self.db.commit()
            raise NotAuthenticated()

        tokens = self._issue_tokens(user.id, session.workspace_id, client, session.family_id)
        session.replaced_by_id = tokens.session.id
        session.rotated_at = now
        await self.db.commit()
        return tokens

    async def logout(self, *, session_id: uuid.UUID | None, refresh_token: str | None) -> None:
        session: AuthSession | None = None
        if session_id is not None:
            session = await users_repo.get_session(self.db, session_id)
        if session is None and refresh_token:
            session = await users_repo.get_session_by_hash(self.db, hash_token(refresh_token))
        if session is not None:
            await users_repo.revoke_family(self.db, session.family_id)
            system_repo.add_audit(
                self.db,
                action="auth.logout",
                workspace_id=None,
                actor_user_id=session.user_id,
            )
            await self.db.commit()

    async def verify_email(self, *, token: str) -> None:
        record = await users_repo.get_valid_token(
            self.db, hash_token(token), TokenPurpose.verify_email
        )
        if record is None:
            raise InvalidToken()
        user = await users_repo.get_user(self.db, record.user_id)
        if user is None:
            raise InvalidToken()
        record.used_at = users_repo.utcnow()
        if user.email_verified_at is None:
            user.email_verified_at = users_repo.utcnow()
        system_repo.add_audit(self.db, action="auth.email_verified", actor_user_id=user.id)
        await self.db.commit()

    async def resend_verification(self, *, user: User) -> None:
        await enforce(self.limiter, f"resend:user:{user.id}", 3, 3600)
        if user.email_verified_at is not None:
            return
        await users_repo.invalidate_tokens(self.db, user.id, TokenPurpose.verify_email)
        self._queue_verification(user)
        await self.db.commit()

    async def forgot_password(self, *, email: str, client: ClientInfo) -> None:
        """Always succeeds from the caller's view, so it never reveals whether an account exists."""
        email = normalize_email(email)
        await enforce(self.limiter, f"forgot:ip:{client.ip}", 10, 3600)
        if not await self.limiter.hit(f"forgot:email:{email}", 3, 3600):
            return
        user = await users_repo.get_user_by_email(self.db, email)
        if user is None or not user.is_active:
            return
        await users_repo.invalidate_tokens(self.db, user.id, TokenPurpose.reset_password)
        self._queue_token_email(
            user,
            TokenPurpose.reset_password,
            timedelta(minutes=self.settings.password_reset_ttl_minutes),
            emails.RESET_PASSWORD,
            "/reset-password",
        )
        system_repo.add_audit(
            self.db,
            action="auth.password_reset_requested",
            actor_user_id=user.id,
            ip_hash=hash_ip(self.settings, client.ip),
        )
        await self.db.commit()

    async def reset_password(self, *, token: str, password: str, client: ClientInfo) -> None:
        await enforce(self.limiter, f"reset:ip:{client.ip}", 10, 3600)
        record = await users_repo.get_valid_token(
            self.db, hash_token(token), TokenPurpose.reset_password
        )
        if record is None:
            raise InvalidToken()
        user = await users_repo.get_user(self.db, record.user_id)
        if user is None or not user.is_active:
            raise InvalidToken()
        record.used_at = users_repo.utcnow()
        user.password_hash = hash_password(password)
        if user.email_verified_at is None:  # following the emailed link proves inbox ownership
            user.email_verified_at = users_repo.utcnow()
        await users_repo.invalidate_tokens(self.db, user.id, TokenPurpose.reset_password)
        await users_repo.revoke_all_sessions(self.db, user.id)
        system_repo.add_audit(
            self.db,
            action="auth.password_reset",
            actor_user_id=user.id,
            ip_hash=hash_ip(self.settings, client.ip),
        )
        await self.db.commit()

    async def change_password(
        self,
        *,
        user: User,
        workspace_id: uuid.UUID,
        current_password: str,
        new_password: str,
        keep_family: uuid.UUID,
    ) -> None:
        await enforce(self.limiter, f"change-password:user:{user.id}", 10, 3600)
        if not verify_password(current_password, user.password_hash).valid:
            raise WrongPassword()
        user.password_hash = hash_password(new_password)
        await users_repo.revoke_all_sessions(self.db, user.id, except_family=keep_family)
        system_repo.add_audit(
            self.db,
            action="auth.password_changed",
            workspace_id=workspace_id,
            actor_user_id=user.id,
        )
        await self.db.commit()
