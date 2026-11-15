"""Run extraction in a child process with a hard timeout.

Parsers are the largest attack surface (malformed PDFs, zip bombs). Isolating them means a hang
is killed, a crash or out-of-memory kill becomes a clean failure, and the worker survives.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import time
from multiprocessing.connection import Connection
from pathlib import Path

from app.ingestion.extractors import Extraction, ExtractionError, extract


class ExtractionTimeout(ExtractionError):
    def __init__(self, seconds: int) -> None:
        super().__init__(
            "extract_timeout",
            f"Processing took longer than {seconds} seconds. The file may be too large or complex.",
        )


def _child(path: str, ext: str, conn: Connection) -> None:
    try:
        conn.send(("ok", extract(path, ext)))
    except ExtractionError as exc:
        conn.send(("error", exc.code, exc.message))
    except Exception as exc:  # report, never raise across the process boundary
        conn.send(("crash", type(exc).__name__))
    finally:
        conn.close()


async def run_extraction(path: Path, ext: str, timeout_seconds: int) -> Extraction:
    ctx = mp.get_context("forkserver")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(str(path), ext, sender), daemon=True)
    process.start()
    sender.close()
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            # Read before joining: a large result fills the pipe and blocks the child until read.
            if receiver.poll():
                message = receiver.recv()
                break
            if not process.is_alive():
                if receiver.poll():
                    message = receiver.recv()
                    break
                raise ExtractionError(
                    "extract_crashed",
                    "The file could not be processed. It may be damaged, too large or too complex.",
                )
            if time.monotonic() > deadline:
                raise ExtractionTimeout(timeout_seconds)
            await asyncio.sleep(0.1)
    finally:
        if process.is_alive():
            process.kill()
        process.join(timeout=5)
        receiver.close()

    status = message[0]
    if status == "ok":
        result: Extraction = message[1]
        return result
    if status == "error":
        raise ExtractionError(message[1], message[2])
    raise ExtractionError("extract_failed", "The file could not be processed.")
