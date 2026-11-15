"""Shared HTTP plumbing for AI providers: typed errors and retry with exponential backoff."""

from __future__ import annotations

import asyncio
import random

import httpx

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class ProviderError(Exception):
    """A provider call failed. `message` is safe to log (never contains keys or prompts)."""

    def __init__(
        self, provider: str, message: str, *, status: int | None = None, retryable: bool = False
    ) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.message = message
        self.status = status
        self.retryable = retryable


class ProviderNotConfigured(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(provider, f"no API key configured for {provider}", retryable=False)


def _error_from(provider: str, response: httpx.Response) -> ProviderError:
    status = response.status_code
    if status in (401, 403):
        return ProviderError(provider, f"rejected the API key (HTTP {status})", status=status)
    detail = ""
    try:
        body = response.json()
        detail = (
            str((body.get("error") or {}).get("message", ""))[:200]
            if isinstance(body, dict)
            else ""
        )
    except ValueError:
        pass
    return ProviderError(
        provider,
        f"HTTP {status} {detail}".strip(),
        status=status,
        retryable=status in RETRYABLE_STATUS,
    )


def backoff(attempt: int, base: float = 1.0, cap: float = 20.0) -> float:
    return float(min(cap, base * 2**attempt) + random.uniform(0, 0.5))  # noqa: S311 - jitter


async def post_json(
    client: httpx.AsyncClient,
    provider: str,
    url: str,
    *,
    json: object,
    headers: dict[str, str],
    attempts: int = 4,
) -> httpx.Response:
    """POST with retries on transient failures (429, 5xx, timeouts). Raises ProviderError."""
    last: ProviderError | None = None
    for attempt in range(attempts):
        try:
            response = await client.post(url, json=json, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = ProviderError(provider, f"network error: {type(exc).__name__}", retryable=True)
        else:
            if response.is_success:
                return response
            last = _error_from(provider, response)
            if not last.retryable:
                raise last
        if attempt < attempts - 1:
            await asyncio.sleep(backoff(attempt))
    assert last is not None
    raise last


def error_from_response(provider: str, response: httpx.Response) -> ProviderError:
    return _error_from(provider, response)
