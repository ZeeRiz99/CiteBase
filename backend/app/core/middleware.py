"""Pure ASGI middleware (no response buffering, so SSE streams pass through)."""

from __future__ import annotations

import json
import secrets
from http.cookies import SimpleCookie

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.errors import CsrfFailed, error_body
from app.core.security import csrf_token_is_valid

CSRF_COOKIE = "cb_csrf"
CSRF_HEADER = b"x-csrf-token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode()
        request_id = (
            incoming if 8 <= len(incoming) <= 64 and incoming.isalnum() else secrets.token_hex(8)
        )
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        await self.app(scope, receive, send_with_id)


class CsrfMiddleware:
    """Signed double-submit CSRF check on every unsafe /api request."""

    def __init__(
        self, app: ASGIApp, settings: Settings, exempt_prefixes: tuple[str, ...] = ()
    ) -> None:
        self.app = app
        self.settings = settings
        self.exempt_prefixes = exempt_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in _SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        if not path.startswith("/api/") or path.startswith(self.exempt_prefixes):
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        header_value = headers.get(CSRF_HEADER, b"").decode() or None
        cookie_value = None
        if raw_cookie := headers.get(b"cookie"):
            jar: SimpleCookie = SimpleCookie()
            jar.load(raw_cookie.decode())
            if CSRF_COOKIE in jar:
                cookie_value = jar[CSRF_COOKIE].value

        if csrf_token_is_valid(self.settings, cookie_value, header_value):
            await self.app(scope, receive, send)
            return

        err = CsrfFailed()
        request_id = scope.get("state", {}).get("request_id")
        body = json.dumps(error_body(err.code, err.message, request_id)).encode()
        await send(
            {
                "type": "http.response.start",
                "status": err.status_code,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})
