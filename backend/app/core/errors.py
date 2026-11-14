"""Application error types and the JSON error envelope.

Every error response has the shape {"error": {"code", "message", "request_id", "fields"?}}.
Internal details and stack traces are logged, never returned.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger("errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "The request could not be processed."

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        self.message = message or self.message
        self.code = code or self.code
        super().__init__(self.message)


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"
    message = "Please sign in to continue."


class InvalidCredentials(AppError):
    status_code = 401
    code = "invalid_credentials"
    message = "Invalid email or password."


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to do this."


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with existing data."


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please wait and try again."


class CsrfFailed(AppError):
    status_code = 403
    code = "csrf_failed"
    message = "Your session token is missing or invalid. Refresh the page and try again."


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_body(
    code: str, message: str, request_id: str | None, fields: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if fields:
        body["fields"] = fields
    return {"error": body}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, _request_id(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
                "message": err.get("msg", "Invalid value"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error", "Some fields are invalid.", _request_id(request), fields
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = (
            "The requested resource was not found." if exc.status_code == 404 else str(exc.detail)
        )
        return JSONResponse(
            status_code=exc.status_code, content=error_body(code, message, _request_id(request))
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path, request_id=_request_id(request))
        return JSONResponse(
            status_code=500,
            content=error_body(
                "internal_error",
                "Something went wrong on our side. Please try again.",
                _request_id(request),
            ),
        )
