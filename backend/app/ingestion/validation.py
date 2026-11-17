"""Upload validation: extension allow-list, real file type (magic bytes), limits.

Nothing here executes or renders uploaded content. Parsers run later, in the worker, inside a
child process with a timeout (see ingestion/runner.py).
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from app.core.errors import AppError

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": DOCX_MIME,
    ".txt": "text/plain",
    ".md": "text/markdown",
    # Images are read with text recognition (OCR) in the worker.
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
IMAGE_SIGNATURES: dict[str, tuple[bytes, str]] = {
    ".png": (b"\x89PNG\r\n\x1a\n", "PNG"),
    ".jpg": (b"\xff\xd8\xff", "JPEG"),
    ".jpeg": (b"\xff\xd8\xff", "JPEG"),
}

# Zip-bomb guards for DOCX (a DOCX is a ZIP archive).
MAX_DOCX_UNCOMPRESSED = 300 * 1024 * 1024
MAX_DOCX_ENTRIES = 5000
MAX_DOCX_RATIO = 150


class UploadRejected(AppError):
    status_code = 422
    code = "upload_rejected"
    message = "This file cannot be uploaded."


class FileTooLarge(UploadRejected):
    status_code = 413
    code = "file_too_large"


@dataclass(frozen=True)
class FileFacts:
    ext: str
    mime_type: str
    page_count: int | None


def sanitize_filename(name: str) -> str:
    """Keep a display-safe base name: no paths, no control characters, at most 255 chars."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = unicodedata.normalize("NFC", base)
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C").strip(" .")
    if not base:
        base = "document"
    if len(base) > 255:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: 250 - len(ext)] + dot + ext) if dot else base[:255]
    return base


def extension_of(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_TYPES:
        raise UploadRejected(
            "Unsupported file type. Upload a PDF, Word (.docx), Markdown (.md), text, PNG or JPEG "
            "file.",
            code="unsupported_type",
        )
    return ext


def decode_text(data: bytes) -> str:
    """Decode a text upload. UTF-8 (with or without BOM), UTF-16 with BOM, else Windows-1252."""
    if b"\x00" in data and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise UploadRejected("This text file contains binary data.", code="binary_text")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1252")
    except UnicodeDecodeError as exc:
        raise UploadRejected(
            "This text file uses an unsupported encoding. Save it as UTF-8 and try again.",
            code="text_encoding",
        ) from exc


def _check_pdf(path: Path, max_pages: int) -> int:
    with path.open("rb") as fh:
        if not fh.read(1024).lstrip().startswith(b"%PDF-"):
            raise UploadRejected("This file is not a valid PDF.", code="type_mismatch")
    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise UploadRejected(
                "This PDF is password-protected. Remove the password and upload it again.",
                code="pdf_encrypted",
            ) from exc
        raise UploadRejected("This PDF is damaged and cannot be read.", code="pdf_corrupt") from exc
    try:
        pages = len(pdf)
    finally:
        pdf.close()
    if pages == 0:
        raise UploadRejected("This PDF has no pages.", code="pdf_empty")
    if pages > max_pages:
        raise UploadRejected(
            f"This PDF has {pages} pages. The limit is {max_pages} pages per file.",
            code="pdf_too_many_pages",
        )
    return pages


def _check_docx(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise UploadRejected("This file is not a valid Word document.", code="type_mismatch")
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise UploadRejected("This Word document is damaged.", code="docx_corrupt") from exc
    names = {i.filename for i in infos}
    if "word/document.xml" not in names or "[Content_Types].xml" not in names:
        raise UploadRejected("This file is not a valid Word document.", code="type_mismatch")
    if any(n.lower().endswith("vbaproject.bin") for n in names):
        raise UploadRejected("Macro-enabled documents are not accepted.", code="docx_macros")
    uncompressed = sum(i.file_size for i in infos)
    compressed = sum(i.compress_size for i in infos) or 1
    if (
        len(infos) > MAX_DOCX_ENTRIES
        or uncompressed > MAX_DOCX_UNCOMPRESSED
        or uncompressed / compressed > MAX_DOCX_RATIO
    ):
        raise UploadRejected("This Word document is too complex to process.", code="docx_bomb")


def _check_image(path: Path, ext: str, max_megapixels: int) -> None:
    """Signature, format and size only: reading the header does not decode the pixels."""
    signature, expected = IMAGE_SIGNATURES[ext]
    with path.open("rb") as fh:
        if not fh.read(len(signature)) == signature:
            raise UploadRejected(
                f"This file is not a valid {expected} image.", code="type_mismatch"
            )
    try:
        with Image.open(path) as img:
            fmt, (width, height) = img.format, img.size
    except (OSError, Image.DecompressionBombError) as exc:
        raise UploadRejected(
            "This image is damaged and cannot be read.", code="image_corrupt"
        ) from exc
    if fmt != expected:
        raise UploadRejected(f"This file is not a valid {expected} image.", code="type_mismatch")
    if width * height > max_megapixels * 1_000_000:
        raise UploadRejected(
            f"This image is {width} x {height} pixels. The limit is {max_megapixels} megapixels; "
            "scan at 300 DPI or resize it.",
            code="image_too_large",
        )


def inspect_file(
    path: Path, ext: str, *, max_pdf_pages: int, max_image_megapixels: int = 40
) -> FileFacts:
    """Verify the stored file really is what its extension claims."""
    page_count: int | None = None
    if ext == ".pdf":
        page_count = _check_pdf(path, max_pdf_pages)
    elif ext == ".docx":
        _check_docx(path)
    elif ext in IMAGE_SIGNATURES:
        _check_image(path, ext, max_image_megapixels)
        page_count = 1
    else:
        text = decode_text(path.read_bytes())
        if not text.strip():
            raise UploadRejected("This file is empty.", code="empty_file")
    return FileFacts(ext=ext, mime_type=ALLOWED_TYPES[ext], page_count=page_count)
