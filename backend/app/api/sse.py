"""Streaming response for chat turns.

Starlette cancels a streaming response when the client disconnects (the Stop button aborts the
request). If the body generator is suspended at a `yield` at that moment, nothing would close
it until garbage collection, so its cleanup (saving the partial answer as `stopped`) would run
late or never. This response always closes the generator, shielded from cancellation.
"""

from __future__ import annotations

import anyio
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"

    def __init__(self, content: object, **kwargs: object) -> None:
        super().__init__(content, **kwargs)  # type: ignore[arg-type]
        self.headers["Cache-Control"] = "no-cache, no-store"
        self.headers["X-Accel-Buffering"] = "no"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            close = getattr(self.body_iterator, "aclose", None)
            if close is not None:
                with anyio.CancelScope(shield=True):
                    await close()
