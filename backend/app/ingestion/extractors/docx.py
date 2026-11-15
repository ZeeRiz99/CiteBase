"""DOCX extraction: body paragraphs and tables in document order, split into sections by
heading style. Tables become Markdown; list items become "- " lines."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.extractors.base import (
    ExtractedPage,
    Extraction,
    ExtractionError,
    normalize_text,
    table_to_markdown,
)
from app.ingestion.extractors.text import SectionBuilder

_HEADING = re.compile(r"^heading (\d)$", re.IGNORECASE)


def _heading_level(paragraph: Paragraph) -> int | None:
    name = (paragraph.style.name if paragraph.style is not None else "") or ""
    if name.lower() == "title":
        return 1
    match = _HEADING.match(name)
    return int(match.group(1)) if match else None


def _is_list(paragraph: Paragraph) -> bool:
    name = (paragraph.style.name if paragraph.style is not None else "") or ""
    if "list" in name.lower():
        return True
    ppr = paragraph._p.pPr  # numbering properties mark bulleted/numbered paragraphs
    return ppr is not None and ppr.numPr is not None


def _table_rows(table: Table) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    for row in table.rows:
        cells: list[str | None] = []
        previous: Any = None
        for cell in row.cells:
            # Merged cells repeat the same object; keep the text once.
            cells.append("" if cell._tc is previous else cell.text)
            previous = cell._tc
        rows.append(cells)
    return rows


def extract_docx(path: Path) -> Extraction:
    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise ExtractionError("docx_unreadable", "This Word document could not be read.") from exc

    builder = SectionBuilder()
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            level = _heading_level(paragraph)
            if level is not None:
                builder.heading(level, text)
            elif _is_list(paragraph):
                builder.line(f"- {text}")
            else:
                builder.block(text)
        elif child.tag == qn("w:tbl"):
            markdown = table_to_markdown(_table_rows(Table(child, document)))
            if markdown:
                builder.block(markdown)

    pages = builder.pages(normalize_text)
    if not pages:
        raise ExtractionError("no_text", "This Word document contains no text.")
    return Extraction(pages=pages, extractor="python-docx", extractor_version="1")


__all__ = ["ExtractedPage", "extract_docx"]
