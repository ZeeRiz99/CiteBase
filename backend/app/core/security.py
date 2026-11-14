"""Password hashing, access tokens, opaque tokens and CSRF tokens."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

# argon2-cffi defaults follow RFC 9106's recommended low-memory Argon2id profile.
_hasher = PasswordHasher()
# Used to equalize timing when the email is unknown.
_DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-real-password")

JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class PasswordCheck:
    valid: bool
    needs_rehash: bool = False


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> PasswordCheck:
    if password_hash is None:
        with contextlib.suppress(VerificationError):
            _hasher.verify(_DUMMY_HASH, password)
        return PasswordCheck(valid=False)
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return PasswordCheck(valid=False)
    return PasswordCheck(valid=True, needs_rehash=_hasher.check_needs_rehash(password_hash))


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    session_id: uuid.UUID


def create_access_token(settings: Settings, claims: AccessClaims) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(claims.user_id),
        "wid": str(claims.workspace_id),
        "sid": str(claims.session_id),
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.derive_key("jwt-access"), algorithm=JWT_ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> AccessClaims | None:
    try:
        payload = jwt.decode(
            token,
            settings.derive_key("jwt-access"),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "wid", "sid", "exp", "typ"]},
        )
        if payload.get("typ") != "access":
            return None
        return AccessClaims(
            user_id=uuid.UUID(payload["sub"]),
            workspace_id=uuid.UUID(payload["wid"]),
            session_id=uuid.UUID(payload["sid"]),
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def new_opaque_token() -> tuple[str, str]:
    """Return (raw token for the client, sha256 hash for storage)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_csrf_token(settings: Settings) -> str:
    """Signed double-submit token: random value plus HMAC, so a planted cookie fails."""
    nonce = secrets.token_urlsafe(24)
    sig = hmac.new(settings.derive_key("csrf"), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{sig}"


def csrf_token_is_valid(
    settings: Settings, cookie_value: str | None, header_value: str | None
) -> bool:
    if not cookie_value or not header_value:
        return False
    if not hmac.compare_digest(cookie_value, header_value):
        return False
    nonce, _, sig = cookie_value.partition(".")
    if not nonce or not sig:
        return False
    expected = hmac.new(settings.derive_key("csrf"), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def hash_ip(settings: Settings, ip: str | None) -> str | None:
    if not ip:
        return None
    return hmac.new(settings.derive_key("ip-hash"), ip.encode(), hashlib.sha256).hexdigest()[:32]
