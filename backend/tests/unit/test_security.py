from __future__ import annotations

import uuid

import pytest

from app.core.config import Settings
from app.core.logging import REDACTED, redact_processor
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import (
    AccessClaims,
    create_access_token,
    csrf_token_is_valid,
    decode_access_token,
    hash_password,
    hash_token,
    new_csrf_token,
    new_opaque_token,
    verify_password,
)
from app.db.ids import uuid7

SECRET = "unit-test-secret-key-0123456789-abcdefghijkl"


def make_settings(secret: str = SECRET) -> Settings:
    return Settings(database_url="postgresql+psycopg://x/y", secret_key=secret)  # type: ignore[arg-type]


def test_password_hash_roundtrip_uses_argon2id() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct-horse-battery", hashed).valid
    assert not verify_password("wrong-password", hashed).valid


def test_verify_password_with_unknown_user_is_invalid() -> None:
    assert not verify_password("anything", None).valid


def test_short_secret_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        make_settings("too-short")


def test_access_token_roundtrip_and_tamper_detection() -> None:
    settings = make_settings()
    claims = AccessClaims(user_id=uuid7(), workspace_id=uuid7(), session_id=uuid7())
    token = create_access_token(settings, claims)
    assert decode_access_token(settings, token) == claims
    assert decode_access_token(settings, token[:-2] + "xx") is None
    other = make_settings("another-secret-key-0123456789-abcdefghijkl")
    assert decode_access_token(other, token) is None


def test_derived_keys_are_independent() -> None:
    settings = make_settings()
    assert settings.derive_key("jwt-access") != settings.derive_key("csrf")


def test_csrf_token_validation() -> None:
    settings = make_settings()
    token = new_csrf_token(settings)
    assert csrf_token_is_valid(settings, token, token)
    assert not csrf_token_is_valid(settings, token, None)
    assert not csrf_token_is_valid(settings, None, token)
    assert not csrf_token_is_valid(settings, token, new_csrf_token(settings))
    forged = "attacker-nonce.deadbeef"
    assert not csrf_token_is_valid(settings, forged, forged)


def test_opaque_token_is_stored_as_hash() -> None:
    raw, stored = new_opaque_token()
    assert raw != stored
    assert hash_token(raw) == stored
    assert len(stored) == 64


def test_uuid7_version_variant_and_ordering() -> None:
    ids = [uuid7() for _ in range(200)]
    assert all(i.version == 7 for i in ids)
    assert all(i.variant == uuid.RFC_4122 for i in ids)
    timestamps = [i.int >> 80 for i in ids]
    assert timestamps == sorted(timestamps)


def test_log_redaction() -> None:
    event = redact_processor(
        None,
        "info",
        {
            "event": "login",
            "password": "hunter2",
            "headers": {"Authorization": "Bearer abc", "accept": "json"},
            "refresh_token": "xyz",
        },
    )
    assert event["password"] == REDACTED
    assert event["refresh_token"] == REDACTED
    assert event["headers"]["Authorization"] == REDACTED
    assert event["headers"]["accept"] == "json"


async def test_rate_limiter_sliding_window() -> None:
    limiter = InMemoryRateLimiter()
    results = [await limiter.hit("k", 3, 60) for _ in range(5)]
    assert results == [True, True, True, False, False]
    assert await limiter.hit("other", 3, 60)
