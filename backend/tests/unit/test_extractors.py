from __future__ import annotations

import io
from pathlib import Path

import docx
import pytest

from app.ingestion.extractors import ExtractionError, extract
from tests.fixtures import factory


def write(tmp_path: Path, name: str, data: bytes | str) -> Path:
    path = tmp_path / name
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def test_pdf_text_pages_and_header_footer_removal(tmp_path: Path) -> None:
    pages = [
        factory.LEAVE_POLICY,
        "Expenses are reimbursed monthly.",
        "Remote work needs approval.",
    ]
    result = extract(write(tmp_path, "a.pdf", factory.pdf_with_text(pages)), ".pdf")
    assert result.page_count == 3
    assert not result.needs_ocr
    assert [p.number for p in result.pages] == [1, 2, 3]
    assert "twenty days of annual leave" in result.pages[0].text
    joined = "\n".join(p.text for p in result.pages)
    assert "Confidential" not in joined  # repeated header removed
    assert "Page 2" not in joined  # page-number footer removed


def test_pdf_tables_become_markdown(tmp_path: Path) -> None:
    result = extract(write(tmp_path, "t.pdf", factory.pdf_with_table()), ".pdf")
    text = result.pages[0].text
    assert "| Region | Standard (days) | Express (days) | Price (EUR) |" in text
    assert "| France | 3-4 | 2 | 6.90 |" in text
    # Running text before and after the table survives, in reading order.
    assert text.index("Shipping rates") < text.index("| Region") < text.index("ship free")


def test_scanned_pdf_needs_ocr(tmp_path: Path) -> None:
    result = extract(write(tmp_path, "s.pdf", factory.scanned_pdf()), ".pdf")
    assert result.needs_ocr
    assert result.page_count == 2


def test_docx_sections_tables_and_lists(tmp_path: Path) -> None:
    result = extract(write(tmp_path, "h.docx", factory.docx_document()), ".docx")
    paths = [p.heading_path for p in result.pages]
    assert ("Employee Handbook",) in paths
    assert ("Employee Handbook", "Annual leave") in paths
    leave = next(p for p in result.pages if p.heading_path[-1:] == ("Annual leave",))
    assert "twenty days of annual leave" in leave.text
    assert "- Carry over requests\n- Sick leave is separate" in leave.text
    expenses = next(p for p in result.pages if p.heading_path[-1:] == ("Expenses",))
    assert "| Item | Limit |" in expenses.text
    assert "| Hotel | 150 EUR/night |" in expenses.text


def test_markdown_sections_ignore_headings_in_code(tmp_path: Path) -> None:
    result = extract(write(tmp_path, "r.md", factory.MARKDOWN), ".md")
    titles = [p.heading_label for p in result.pages]
    assert titles == [
        "Returns policy",
        "Returns policy › Time limits",
        "Returns policy › Condition",
    ]
    condition = result.pages[-1].text
    assert "# not a heading" in condition
    assert "| Damaged in transit | Full plus shipping |" in condition


def test_text_with_windows_encoding_and_form_feeds(tmp_path: Path) -> None:
    data = "Café opening hours.\fSecond page – with dash.".encode("cp1252")
    result = extract(write(tmp_path, "w.txt", data), ".txt")
    assert [p.text for p in result.pages] == ["Café opening hours.", "Second page – with dash."]


def test_empty_docx_is_an_error(tmp_path: Path) -> None:
    buf = io.BytesIO()
    docx.Document().save(buf)
    with pytest.raises(ExtractionError) as err:
        extract(write(tmp_path, "e.docx", buf.getvalue()), ".docx")
    assert err.value.code == "no_text"
