from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

HEADING_SEPARATOR = f" {chr(0x203A)} "  # single right-pointing angle quote between levels
_NBSP = chr(0x00A0)


class ExtractionError(Exception):
    """A file that cannot produce usable text. `message` is safe to show to users."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ExtractedPage:
    number: int  # PDF page number, or section ordinal (1-based)
    text: str
    heading_path: tuple[str, ...] = ()

    @property
    def heading_label(self) -> str | None:
        return HEADING_SEPARATOR.join(self.heading_path) or None


@dataclass
class Extraction:
    pages: list[ExtractedPage]
    extractor: str
    extractor_version: str
    page_count: int | None = None
    needs_ocr: bool = False
    warnings: list[str] = field(default_factory=list)
    # Text recognition: how many pages were read by OCR and their mean word confidence (0-100).
    ocr_pages: int = 0
    ocr_confidence: float | None = None

    @property
    def total_chars(self) -> int:
        return sum(len(p.text) for p in self.pages)


def normalize_text(text: str) -> str:
    """NFKC (folds ligatures), unify newlines, trim trailing spaces, collapse 3+ blank lines."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(_NBSP, " ").replace("\t", "    ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def table_to_markdown(rows: list[list[str | None]]) -> str | None:
    """Render a table as Markdown. Returns None for tables too small to be useful."""
    cleaned = [
        [re.sub(r"\s+", " ", (cell or "")).strip().replace("|", "\\|") for cell in row]
        for row in rows
    ]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if len(cleaned) < 2:
        return None
    width = max(len(row) for row in cleaned)
    if width < 2:
        return None
    cleaned = [row + [""] * (width - len(row)) for row in cleaned]
    header, *body = cleaned
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)
