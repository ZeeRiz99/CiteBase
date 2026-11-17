"""Text recognition (Tesseract) end to end: accuracy on generated scans with known text, and the
ingestion paths for scanned PDFs, partially scanned PDFs and PNG/JPEG images."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.ingestion.ocr import OcrOptions, ocr_pdf
from tests.conftest import Api, Mailbox
from tests.fixtures import factory
from tests.integration.test_documents import DOCS, signed_in, upload_and_index  # noqa: F401

pytestmark = pytest.mark.usefixtures("signed_in")


def words(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def char_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein distance / reference length, on whitespace-normalised text."""
    ref, hyp = words(reference), words(hypothesis)
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, 1):
        cur = [i]
        for j, hc in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / max(1, len(ref))


async def chunk_text(api: Api, document_id: str) -> str:
    chunks = (await api.get(f"{DOCS}/{document_id}/chunks")).json()["items"]
    return " ".join(c["text"] for c in chunks)


def test_recognition_accuracy_on_generated_scans(tmp_path: Path) -> None:
    """Tilted, noisy, blurred, JPEG-compressed pages at 200 DPI: under 3% character errors."""
    path = tmp_path / "scan.pdf"
    path.write_bytes(factory.scanned_text_pdf())
    result = ocr_pdf(path, OcrOptions())
    assert result.ocr_pages == 2 and not result.needs_ocr
    assert result.ocr_confidence is not None and result.ocr_confidence > 80
    for page, expected in zip(result.pages, factory.WAREHOUSE_NOTICE, strict=True):
        printed = f"{expected} Page {page.number}"  # the page footer is printed on the scan too
        cer = char_error_rate(printed.replace("\n\n", " "), page.text)
        assert cer < 0.03, f"page {page.number}: CER {cer:.3f}\n{page.text}"


async def test_scanned_pdf_is_recognized_and_searchable(api: Api, mailbox: Mailbox) -> None:
    detail = await upload_and_index(
        api, mailbox, "Warehouse Notice.pdf", factory.scanned_text_pdf()
    )
    latest = detail["latest"]
    assert latest["status"] == "indexed", latest
    assert latest["ocr_pages"] == 2
    assert latest["ocr_confidence"] > 80
    text = await chunk_text(api, detail["id"])
    assert "Leeds warehouse" in text
    assert "Priya Kapoor" in text


async def test_photo_jpeg_is_recognized(api: Api, mailbox: Mailbox) -> None:
    detail = await upload_and_index(api, mailbox, "Delivery Note.jpg", factory.photo_jpeg())
    latest = detail["latest"]
    assert latest["status"] == "indexed", latest
    assert latest["file_ext"] == ".jpg" and latest["ocr_pages"] == 1
    assert "Harbour Street" in await chunk_text(api, detail["id"])
    download = await api.get(f"{DOCS}/{detail['id']}/file")
    assert download.headers["content-type"].startswith("image/jpeg")


async def test_only_scanned_pages_of_a_mixed_pdf_are_recognized(api: Api, mailbox: Mailbox) -> None:
    detail = await upload_and_index(api, mailbox, "Mixed.pdf", factory.partially_scanned_pdf())
    latest = detail["latest"]
    assert latest["status"] == "indexed", latest
    assert latest["ocr_pages"] == 1  # page 1 had a text layer
    text = await chunk_text(api, detail["id"])
    assert "annual leave" in text  # from the text layer
    assert "north car park" in text  # from the scanned page


async def test_unreadable_image_is_flagged(api: Api, mailbox: Mailbox) -> None:
    detail = await upload_and_index(api, mailbox, "Noise.png", factory.blank_scan_png())
    latest = detail["latest"]
    assert latest["status"] == "needs_ocr"
    assert latest["error_code"] == "ocr_no_text"


async def test_ocr_turned_off_or_too_long(api: Api, mailbox: Mailbox, settings: Settings) -> None:
    settings.ocr_enabled = False
    off = await upload_and_index(api, mailbox, "Scan A.pdf", factory.scanned_text_pdf())
    assert off["latest"]["status"] == "needs_ocr"
    assert off["latest"]["error_code"] == "needs_ocr"
    assert "turned off" in off["latest"]["error_message"]

    settings.ocr_enabled = True
    settings.ocr_max_pages = 1
    long = await upload_and_index(
        api, mailbox, "Scan B.pdf", factory.scanned_text_pdf([*factory.WAREHOUSE_NOTICE, "x"])
    )
    assert long["latest"]["error_code"] == "ocr_too_many_pages"
    assert "limited to 1 pages" in long["latest"]["error_message"]


async def test_image_upload_validation(api: Api, settings: Settings) -> None:
    fake = await api.upload("fake.png", b"this is not an image at all")
    assert fake.status_code == 422 and fake.json()["error"]["code"] == "type_mismatch"
    wrong = await api.upload("photo.png", factory.photo_jpeg())  # JPEG bytes, .png name
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "type_mismatch"
    settings.max_image_megapixels = 1
    big = await api.upload("big.png", factory.blank_scan_png())  # 1240 x 1754 = 2.2 MP
    assert big.status_code == 422 and big.json()["error"]["code"] == "image_too_large"
