"""Rate limiting behind a small interface.

V1 runs a single API instance, so an in-process sliding window is correct.
V2 swaps in a Redis implementation of the same protocol.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Protocol

from app.core.errors import RateLimited


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Record one hit. Return False when the key is over its limit."""
        ...

    def reset(self) -> None: ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        async with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        self._hits.clear()


class DisabledRateLimiter:
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        return True

    def reset(self) -> None:
        return None


async def enforce(limiter: RateLimiter, key: str, limit: int, window_seconds: int) -> None:
    if not await limiter.hit(key, limit, window_seconds):
        raise RateLimited()
