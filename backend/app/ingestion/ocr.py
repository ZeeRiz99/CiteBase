"""Text recognition (OCR) with Tesseract for scanned PDF pages and PNG/JPEG images.

Runs inside the extraction child process (ingestion/runner.py), like every parser. PDF pages are
rendered with PDFium; Tesseract's TSV output gives words with confidence and paragraph structure,
which is rebuilt into reflowed paragraphs (hyphenated line breaks re-joined).
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from app.ingestion.extractors.base import (
    ExtractedPage,
    Extraction,
    ExtractionError,
    normalize_text,
)

TESSERACT = "tesseract"
MAX_RENDER_SIDE = 6000  # pixels; caps memory for oversized PDF pages
MIN_OCR_CHARS_PER_PAGE = 25  # fewer recognized characters than this means "nothing readable"
IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg"})


@dataclass(frozen=True)
class OcrOptions:
    languages: str = "eng"
    dpi: int = 300
    page_timeout_seconds: int = 120


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None  # mean word confidence, 0-100; None when no words were found
    words: int


def tesseract_version() -> str:
    try:
        out = subprocess.run(  # noqa: S603 - fixed binary, no user input in the arguments
            [TESSERACT, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExtractionError(
            "ocr_unavailable", "Text recognition is not installed on this server."
        ) from exc
    first = (out.stdout or out.stderr).splitlines()[:1]
    return first[0].removeprefix("tesseract ").strip()[:40] if first else "unknown"


def parse_tsv(tsv: str) -> OcrResult:
    """Rebuild paragraphs from Tesseract TSV (level 5 rows are words)."""
    paragraphs: dict[tuple[int, int, int], dict[int, list[str]]] = {}
    confidences: list[float] = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row.get("level") != "5":
            continue
        word = (row.get("text") or "").strip()
        if not word:
            continue
        try:
            conf = float(row.get("conf") or -1)
        except ValueError:
            conf = -1
        if conf >= 0:
            confidences.append(conf)
        key = (int(row["page_num"]), int(row["block_num"]), int(row["par_num"]))
        paragraphs.setdefault(key, {}).setdefault(int(row["line_num"]), []).append(word)

    blocks: list[str] = []
    for key in sorted(paragraphs):
        lines = [" ".join(words) for _, words in sorted(paragraphs[key].items())]
        text = lines[0]
        for line in lines[1:]:
            if re.search(r"[A-Za-z]-$", text) and line[:1].islower():
                text = text[:-1] + line  # word hyphenated across lines
            else:
                text += " " + line
        blocks.append(text)
    confidence = sum(confidences) / len(confidences) if confidences else None
    return OcrResult(normalize_text("\n\n".join(blocks)), confidence, len(confidences))


def ocr_image(image: Image.Image, options: OcrOptions) -> OcrResult:
    gray = image.convert("L")
    with tempfile.TemporaryDirectory(prefix="cb-ocr-") as tmp:
        src = Path(tmp) / "page.png"
        gray.save(src, format="PNG")
        try:
            out = subprocess.run(  # noqa: S603 - arguments are a temp path and validated options
                [TESSERACT, str(src), "stdout", "-l", options.languages, "--psm", "3", "tsv"],
                capture_output=True,
                text=True,
                timeout=options.page_timeout_seconds,
                check=False,
                # One thread per page: the worker already runs one job at a time.
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
        except FileNotFoundError as exc:
            raise ExtractionError(
                "ocr_unavailable", "Text recognition is not installed on this server."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ExtractionError(
                "ocr_timeout", "Text recognition took too long for one page of this file."
            ) from exc
    if out.returncode != 0:
        raise ExtractionError("ocr_failed", "Text recognition could not read this file.")
    return parse_tsv(out.stdout)


def _render_page(pdf: pdfium.PdfDocument, index: int, dpi: int) -> Image.Image:
    page = pdf[index]
    try:
        width, height = page.get_size()  # points (1/72 inch)
        scale = min(dpi / 72, MAX_RENDER_SIDE / max(width, height, 1))
        image: Image.Image = page.render(scale=scale, grayscale=True).to_pil()
        return image
    finally:
        page.close()


def _extraction(
    pages: list[tuple[int, OcrResult]], page_count: int, warnings: list[str]
) -> Extraction:
    readable = [
        (n, r) for n, r in pages if len(re.sub(r"\s", "", r.text)) >= MIN_OCR_CHARS_PER_PAGE
    ]
    words = sum(r.words for _, r in readable)
    weighted = sum((r.confidence or 0) * r.words for _, r in readable)
    return Extraction(
        pages=[ExtractedPage(number=n, text=r.text) for n, r in readable],
        extractor="tesseract",
        extractor_version=tesseract_version(),
        page_count=page_count,
        needs_ocr=not readable,
        warnings=warnings,
        ocr_pages=len(readable),
        ocr_confidence=round(weighted / words, 1) if words else None,
    )


def ocr_pdf(path: Path, options: OcrOptions, pages: list[int] | None = None) -> Extraction:
    """Recognize the given 1-based pages (all pages when None)."""
    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as exc:
        raise ExtractionError("pdf_unreadable", "This PDF could not be read.") from exc
    try:
        total = len(pdf)
        numbers = [n for n in (pages or range(1, total + 1)) if 1 <= n <= total]
        results = [(n, ocr_image(_render_page(pdf, n - 1, options.dpi), options)) for n in numbers]
    finally:
        pdf.close()
    unreadable = len(numbers) - sum(
        1 for _, r in results if len(re.sub(r"\s", "", r.text)) >= MIN_OCR_CHARS_PER_PAGE
    )
    warnings = (
        [f"Text recognition found no readable text on {unreadable} page(s)."] if unreadable else []
    )
    return _extraction(results, total, warnings)


def ocr_image_file(path: Path, options: OcrOptions) -> Extraction:
    try:
        with Image.open(path) as img:
            image = ImageOps.exif_transpose(img)  # phone photos store rotation in EXIF
            image.load()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ExtractionError("image_unreadable", "This image could not be read.") from exc
    return _extraction([(1, ocr_image(image, options))], 1, [])


def run_ocr(path: str | Path, ext: str, options: OcrOptions, pages: list[int] | None) -> Extraction:
    path = Path(path)
    if ext == ".pdf":
        return ocr_pdf(path, options, pages)
    if ext in IMAGE_EXTS:
        return ocr_image_file(path, options)
    raise ExtractionError("unsupported_type", f"No text recognition for {ext}")
