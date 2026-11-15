"""Text extraction, one module per format. All return an `Extraction`.

Pages are PDF pages, or sections (by heading) for DOCX and Markdown, or the whole file for TXT.
Each extractor is a pure function of the file: no database, no network.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.extractors.base import ExtractedPage, Extraction, ExtractionError
from app.ingestion.extractors.docx import extract_docx
from app.ingestion.extractors.pdf import extract_pdf
from app.ingestion.extractors.text import extract_markdown, extract_text


def extract(path: str | Path, ext: str) -> Extraction:
    path = Path(path)
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".md":
        return extract_markdown(path)
    if ext == ".txt":
        return extract_text(path)
    raise ExtractionError("unsupported_type", f"No extractor for {ext}")


__all__ = ["ExtractedPage", "Extraction", "ExtractionError", "extract"]
