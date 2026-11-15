from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.validation import (
    UploadRejected,
    decode_text,
    extension_of,
    inspect_file,
    sanitize_filename,
)
from tests.fixtures import factory


def check(tmp_path: Path, name: str, data: bytes, ext: str, max_pages: int = 500) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    try:
        inspect_file(path, ext, max_pdf_pages=max_pages)
    except UploadRejected as exc:
        return exc.code
    return "ok"


def test_extension_allow_list() -> None:
    assert extension_of("Report.PDF") == ".pdf"
    with pytest.raises(UploadRejected):
        extension_of("payload.exe")
    with pytest.raises(UploadRejected):
        extension_of("page.html")


def test_real_files_pass(tmp_path: Path) -> None:
    assert check(tmp_path, "a.pdf", factory.pdf_with_text(["Hello world"]), ".pdf") == "ok"
    assert check(tmp_path, "a.docx", factory.docx_document(), ".docx") == "ok"
    assert check(tmp_path, "a.md", factory.MARKDOWN.encode(), ".md") == "ok"


def test_magic_bytes_must_match_extension(tmp_path: Path) -> None:
    assert check(tmp_path, "fake.pdf", b"just text pretending", ".pdf") == "type_mismatch"
    assert check(tmp_path, "fake.docx", b"%PDF-1.4 not a zip", ".docx") == "type_mismatch"


def test_damaged_and_encrypted_pdfs_are_rejected(tmp_path: Path) -> None:
    assert check(tmp_path, "bad.pdf", b"%PDF-1.7\n garbage garbage", ".pdf") == "pdf_corrupt"
    assert check(tmp_path, "enc.pdf", factory.encrypted_pdf(), ".pdf") == "pdf_encrypted"


def test_pdf_page_limit(tmp_path: Path) -> None:
    data = factory.pdf_with_text(["one", "two", "three"])
    assert check(tmp_path, "p.pdf", data, ".pdf", max_pages=2) == "pdf_too_many_pages"


def test_docx_macros_and_zip_bombs_are_rejected(tmp_path: Path) -> None:
    assert check(tmp_path, "m.docx", factory.docx_with_macro(), ".docx") == "docx_macros"
    assert check(tmp_path, "b.docx", factory.docx_bomb(), ".docx") == "docx_bomb"


def test_text_must_be_text(tmp_path: Path) -> None:
    assert check(tmp_path, "bin.txt", b"abc\x00\x01\x02", ".txt") == "binary_text"
    assert check(tmp_path, "empty.md", b"   \n  ", ".md") == "empty_file"
    assert decode_text("naïve".encode("utf-16")) == "naïve"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\Report.pdf", "Report.pdf"),
        ("bad\x00name\x07.txt", "badname.txt"),
        ("", "document"),
        ("..", "document"),
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_and_keeps_extension() -> None:
    name = sanitize_filename("x" * 400 + ".pdf")
    assert len(name) <= 255
    assert name.endswith(".pdf")
