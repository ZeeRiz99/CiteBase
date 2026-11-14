"""Auth cookie names and helpers.

- cb_access: short-lived JWT, httpOnly, sent to /api only.
- cb_refresh: rotating opaque token, httpOnly, sent only to /api/v1/auth.
- cb_session: non-secret "signed in" marker (value "1") so the frontend can redirect early.
- cb_csrf: signed double-submit token, readable by the frontend.
"""

from __future__ import annotations

from fastapi import Response

from app.core.config import Settings
from app.core.middleware import CSRF_COOKIE
from app.core.security import new_csrf_token
from app.services.auth import IssuedTokens

ACCESS_COOKIE = "cb_access"
REFRESH_COOKIE = "cb_refresh"
SESSION_MARKER_COOKIE = "cb_session"
REFRESH_PATH = "/api/v1/auth"


def set_auth_cookies(response: Response, settings: Settings, tokens: IssuedTokens) -> None:
    secure = settings.cookie_secure
    refresh_age = settings.refresh_token_ttl_days * 86400
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        path="/api",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=refresh_age,
        path=REFRESH_PATH,
        httponly=True,
        secure=secure,
        samesite="strict",
    )
    response.set_cookie(
        SESSION_MARKER_COOKIE,
        "1",
        max_age=refresh_age,
        path="/",
        httponly=False,  # holds no secret; lets the UI skip /me calls when signed out
        secure=secure,
        samesite="lax",
    )
    set_csrf_cookie(response, settings)


def set_csrf_cookie(response: Response, settings: Settings) -> str:
    token = new_csrf_token(settings)
    response.set_cookie(
        CSRF_COOKIE, token, path="/", httponly=False, secure=settings.cookie_secure, samesite="lax"
    )
    return token


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(SESSION_MARKER_COOKIE, path="/")
