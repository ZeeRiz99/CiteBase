"""PDF extraction with pdfplumber: reading-order text, tables as Markdown, repeated headers and
footers removed, paragraphs reflowed, scanned PDFs detected (never indexed as empty)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any

import pdfplumber

from app.ingestion.extractors.base import (
    ExtractedPage,
    Extraction,
    ExtractionError,
    normalize_text,
    table_to_markdown,
)

MIN_TEXT_CHARS_PER_PAGE = 25
OCR_TEXT_PAGE_RATIO = 0.5
# Bullets (U+2022 bullet, en dash, small/black squares and circles) and numbered/lettered items.
_BULLETS = "".join(map(chr, (0x2022, 0x2013, 0x25AA, 0x25CF)))
_LIST_MARKER = re.compile(rf"^([-*{_BULLETS}]|\(?\d{{1,3}}[.)]|[a-z][.)])\s")


@dataclass
class _Item:
    top: float
    bottom: float
    text: str
    is_table: bool = False


def _inside(obj: dict[str, Any], bbox: tuple[float, float, float, float]) -> bool:
    x0, top, x1, bottom = bbox
    cx = (obj["x0"] + obj["x1"]) / 2
    cy = (obj["top"] + obj["bottom"]) / 2
    return bool(x0 <= cx <= x1 and top <= cy <= bottom)


def _page_items(page: Any) -> list[_Item]:
    tables = page.find_tables()
    bboxes = [t.bbox for t in tables]
    text_page = page.filter(lambda o: not any(_inside(o, b) for b in bboxes)) if bboxes else page
    items = [
        _Item(top=line["top"], bottom=line["bottom"], text=line["text"])
        for line in text_page.extract_text_lines(strip=True)
        if line["text"].strip()
    ]
    for table in tables:
        markdown = table_to_markdown(table.extract())
        if markdown:
            items.append(
                _Item(top=table.bbox[1], bottom=table.bbox[3], text=markdown, is_table=True)
            )
    items.sort(key=lambda i: i.top)
    return items


def _signature(text: str) -> str:
    return re.sub(r"\d+", "#", text.strip().lower())


def _repeated_margins(pages: list[list[_Item]]) -> set[str]:
    """Lines among the first/last two of most pages: headers, footers, page numbers.

    Two-page documents need the line on both pages; longer ones on at least half of them.
    """
    if len(pages) < 2:
        return set()
    counts: Counter[str] = Counter()
    for items in pages:
        lines = [i for i in items if not i.is_table]
        edge = {_signature(i.text) for i in lines[:2] + lines[-2:]}
        counts.update(edge)
    threshold = len(pages) if len(pages) == 2 else max(2, (len(pages) + 1) // 2)
    return {sig for sig, n in counts.items() if n >= threshold and sig}


def _join_lines(lines: list[_Item]) -> str:
    """Reflow lines into paragraphs: blank line on large vertical gaps, keep list items apart."""
    if not lines:
        return ""
    heights = [max(1.0, line.bottom - line.top) for line in lines]
    line_height = median(heights)
    out: list[str] = [lines[0].text]
    for prev, line in pairwise(lines):
        gap = line.top - prev.bottom
        if gap > line_height * 0.8:
            out.append("\n\n" + line.text)
        elif _LIST_MARKER.match(line.text):
            out.append("\n" + line.text)
        elif re.search(r"[A-Za-z]-$", out[-1]) and line.text[:1].islower():
            out[-1] = out[-1][:-1]  # re-join a word hyphenated across lines
            out.append(line.text)
        else:
            out.append(" " + line.text)
    return "".join(out)


def _render(items: list[_Item], drop: set[str]) -> str:
    blocks: list[str] = []
    run: list[_Item] = []
    for item in items:
        if item.is_table:
            if run:
                blocks.append(_join_lines(run))
                run = []
            blocks.append(item.text)
        elif _signature(item.text) not in drop:
            run.append(item)
    if run:
        blocks.append(_join_lines(run))
    return normalize_text("\n\n".join(b for b in blocks if b.strip()))


def extract_pdf(path: Path) -> Extraction:
    try:
        with pdfplumber.open(str(path)) as pdf:
            raw = [_page_items(page) for page in pdf.pages]
    except Exception as exc:  # pdfminer raises many exception types on malformed input
        raise ExtractionError("pdf_unreadable", "This PDF could not be read.") from exc

    drop = _repeated_margins(raw)
    pages = [ExtractedPage(number=n, text=_render(items, drop)) for n, items in enumerate(raw, 1)]
    text_pages = sum(1 for p in pages if len(re.sub(r"\s", "", p.text)) >= MIN_TEXT_CHARS_PER_PAGE)
    needs_ocr = not pages or text_pages / len(pages) < OCR_TEXT_PAGE_RATIO
    warnings = []
    if not needs_ocr and text_pages < len(pages):
        warnings.append(
            f"{len(pages) - text_pages} page(s) have little or no text and may be scanned."
        )
    return Extraction(
        pages=[p for p in pages if p.text],
        extractor="pdfplumber",
        extractor_version=pdfplumber.__version__,
        page_count=len(pages),
        needs_ocr=needs_ocr,
        warnings=warnings,
    )
