"""Markdown (sections by ATX heading, fenced code respected) and plain-text extraction."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from app.ingestion.extractors.base import (
    ExtractedPage,
    Extraction,
    ExtractionError,
    normalize_text,
)
from app.ingestion.validation import decode_text

_ATX = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


class SectionBuilder:
    """Collects blocks under a heading stack; each heading starts a new section ("page")."""

    def __init__(self) -> None:
        self._stack: list[str] = []
        self._sections: list[tuple[tuple[str, ...], list[str]]] = [((), [])]

    def heading(self, level: int, title: str) -> None:
        title = re.sub(r"\s+", " ", title).strip()
        self._stack = [*self._stack[: level - 1], title]
        self._sections.append((tuple(self._stack), [title]))

    def block(self, text: str) -> None:
        self._sections[-1][1].append(text)

    def line(self, text: str) -> None:
        """Append a line to the previous block when it is also a line item (lists stay together)."""
        blocks = self._sections[-1][1]
        if blocks and blocks[-1].startswith("- ") and text.startswith("- "):
            blocks[-1] += "\n" + text
        else:
            blocks.append(text)

    def pages(self, normalize: Callable[[str], str]) -> list[ExtractedPage]:
        out: list[ExtractedPage] = []
        for path, blocks in self._sections:
            text = normalize("\n\n".join(blocks))
            if text:
                out.append(ExtractedPage(number=len(out) + 1, text=text, heading_path=path))
        return out


def extract_markdown(path: Path) -> Extraction:
    source = normalize_text(decode_text(path.read_bytes()))
    builder = SectionBuilder()
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        if buffer:
            builder.block("\n".join(buffer).strip("\n"))
            buffer.clear()

    for raw in source.split("\n"):
        if _FENCE.match(raw):
            in_fence = not in_fence
            buffer.append(raw)
            continue
        heading = None if in_fence else _ATX.match(raw)
        if heading:
            flush()
            builder.heading(len(heading.group(1)), heading.group(2))
        elif not in_fence and not raw.strip():
            flush()
        else:
            buffer.append(raw)
    flush()

    pages = builder.pages(normalize_text)
    if not pages:
        raise ExtractionError("no_text", "This file contains no text.")
    return Extraction(pages=pages, extractor="markdown", extractor_version="1")


def extract_text(path: Path) -> Extraction:
    text = normalize_text(decode_text(path.read_bytes()))
    if not text:
        raise ExtractionError("no_text", "This file contains no text.")
    # Form feeds mark page breaks in some exported text files.
    parts = [p.strip() for p in text.split("\f")]
    pages = [ExtractedPage(number=i, text=p) for i, p in enumerate((p for p in parts if p), 1)]
    return Extraction(pages=pages, extractor="text", extractor_version="1")
