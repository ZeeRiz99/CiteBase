"""Generate realistic test documents in memory (no binary fixtures in the repo)."""

from __future__ import annotations

import io
import random
import zipfile

import docx
import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageFilter
from reportlab.lib import pdfencrypt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

LEAVE_POLICY = (
    "New employees receive twenty days of annual leave per year. Leave accrues monthly from the "
    "start date. Unused days carry over up to a limit of five days. Requests must be approved by "
    "a line manager at least two weeks in advance."
)


def pdf_with_text(
    pages: list[str], header: str | None = "Northwind Outfitters - Confidential"
) -> bytes:
    """One paragraph block per page, with an optional repeated header and a page-number footer."""
    buf = io.BytesIO()
    styles = getSampleStyleSheet()

    def decorate(c: canvas.Canvas, doc: SimpleDocTemplate) -> None:
        c.saveState()
        c.setFont("Helvetica", 8)
        if header:
            c.drawString(2 * cm, A4[1] - 1.2 * cm, header)
        c.drawString(A4[0] / 2, 1 * cm, f"Page {doc.page}")
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4)
    story: list[object] = []
    for i, text in enumerate(pages):
        for para in text.split("\n\n"):
            story.append(Paragraph(para, styles["BodyText"]))
            story.append(Spacer(1, 0.4 * cm))
        if i < len(pages) - 1:
            story.append(PageBreak())
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()


def pdf_with_table() -> bytes:
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    data = [
        ["Region", "Standard (days)", "Express (days)", "Price (EUR)"],
        ["Germany", "2-3", "1", "4.90"],
        ["France", "3-4", "2", "6.90"],
        ["Spain", "4-6", "2", "7.90"],
    ]
    table = Table(data)
    table.setStyle([("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0))])
    doc.build(
        [
            Paragraph("Shipping rates for European orders are listed below.", styles["BodyText"]),
            Spacer(1, 0.5 * cm),
            table,
            Spacer(1, 0.5 * cm),
            Paragraph("Orders above 50 EUR ship free with standard delivery.", styles["BodyText"]),
        ]
    )
    return buf.getvalue()


def scanned_pdf(pages: int = 2) -> bytes:
    """Image-like pages with no text layer, as a scanner would produce."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for _ in range(pages):
        for row in range(40):
            c.setFillGray(0.2 + (row % 5) * 0.1)
            c.rect(2 * cm, 3 * cm + row * 0.55 * cm, 15 * cm, 0.3 * cm, fill=1, stroke=0)
        c.showPage()
    c.save()
    return buf.getvalue()


def encrypted_pdf() -> bytes:
    buf = io.BytesIO()
    enc = pdfencrypt.StandardEncryption("user-secret", "owner-secret", canPrint=0)
    c = canvas.Canvas(buf, pagesize=A4, encrypt=enc)
    c.drawString(100, 750, "Secret content")
    c.showPage()
    c.save()
    return buf.getvalue()


def docx_document() -> bytes:
    d = docx.Document()
    d.add_heading("Employee Handbook", level=1)
    d.add_paragraph("This handbook describes company policies. It is fictional demo content.")
    d.add_heading("Annual leave", level=2)
    d.add_paragraph(LEAVE_POLICY)
    d.add_paragraph("Carry over requests", style="List Bullet")
    d.add_paragraph("Sick leave is separate", style="List Bullet")
    d.add_heading("Expenses", level=2)
    d.add_paragraph("Submit receipts within thirty days through the finance portal.")
    table = d.add_table(rows=3, cols=2)
    for r, (a, b) in enumerate(
        [("Item", "Limit"), ("Hotel", "150 EUR/night"), ("Meals", "40 EUR/day")]
    ):
        table.cell(r, 0).text = a
        table.cell(r, 1).text = b
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def docx_with_macro() -> bytes:
    src = io.BytesIO(docx_document())
    out = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("word/vbaProject.bin", b"fake macro")
    return out.getvalue()


def docx_bomb() -> bytes:
    """A valid-looking DOCX whose single entry expands far beyond the ratio limit."""
    src = io.BytesIO(docx_document())
    out = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item.filename, zin.read(item.filename))
        zout.writestr("word/media/padding.bin", b"\0" * (40 * 1024 * 1024))
    return out.getvalue()


MARKDOWN = """# Returns policy

Fictional demo content for Northwind Outfitters.

## Time limits

Items can be returned within 30 days of delivery. Sale items can be returned within 14 days.

## Condition

Items must be unused and in their original packaging.

```bash
# not a heading: inside a code block
echo "keep me"
```

| Item type | Refund |
| --- | --- |
| Unused | Full |
| Damaged in transit | Full plus shipping |
"""

TEXT = (
    "Northwind Outfitters support guide. Fictional demo content.\n\n"
    "Customers can reach support by email at any time. Phone support is open on weekdays.\n\n"
    "Warranty claims require the order number and a photo of the defect."
)


# ---- Scanned documents with known text (for text recognition) ---------------------------------

WAREHOUSE_NOTICE = (
    "DEMO DATA: fictional company, for testing only.\n\n"
    "Northwind Outfitters - Warehouse Notice\n\n"
    "From 1 March the returns desk at the Leeds warehouse is open Monday to Friday from 8:00 to "
    "16:00. Parcels that arrive without a returns number are refused and sent back to the sender."
    "\n\n"
    "Forklift training takes place every second Tuesday. Only staff with a valid training card "
    "may drive a forklift in aisles 4 to 9.",
    "Fire drills are held on the first Monday of each quarter at 10:30. The assembly point is the "
    "north car park, next to the bicycle shelter.\n\n"
    "Questions about this notice go to the warehouse manager, Priya Kapoor, on extension 2214.",
)

DELIVERY_NOTE = (
    "DEMO DATA: fictional delivery note.\n\n"
    "Northwind Outfitters - Delivery Note 48213\n\n"
    "Delivered to Harbour Street store on 14 May: 12 Alpine Down Jackets, 30 pairs of Trail Socks "
    "and 6 Summit Tents. Two tents had damaged boxes and were returned with the driver. "
    "Signed by the store supervisor, Tom Reyes."
)


def degrade(page: Image.Image, seed: int = 7) -> Image.Image:
    """Make a clean page look scanned: slight tilt, sensor noise, blur and JPEG artefacts."""
    rnd = random.Random(seed)  # noqa: S311 - reproducible test images, not security
    img = page.convert("L").rotate(
        rnd.uniform(-1.0, 1.0), resample=Image.Resampling.BICUBIC, fillcolor=255
    )
    noise = Image.effect_noise(img.size, 14)  # Gaussian around 128
    img = ImageChops.add(img, noise, scale=1.0, offset=-128)
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def page_images(pages: list[str] | tuple[str, ...], dpi: int = 200) -> list[Image.Image]:
    """Render text pages (laid out like pdf_with_text) to grayscale images."""
    pdf = pdfium.PdfDocument(pdf_with_text(list(pages), header=None))
    try:
        return [pdf[i].render(scale=dpi / 72, grayscale=True).to_pil() for i in range(len(pdf))]
    finally:
        pdf.close()


def _image_pdf(pages: list[Image.Image | str]) -> bytes:
    """A PDF whose pages are images (scans) or, for strings, a real text layer."""
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    c = canvas.Canvas(buf, pagesize=A4)
    for page in pages:
        if isinstance(page, str):
            top = A4[1] - 2.5 * cm
            for para in page.split("\n\n"):
                p = Paragraph(para, styles["BodyText"])
                _, height = p.wrap(A4[0] - 4 * cm, A4[1])
                p.drawOn(c, 2 * cm, top - height)
                top -= height + 0.4 * cm
        else:
            # Embedded as JPEG, like a real scanner's output (and a small file).
            jpeg = io.BytesIO()
            page.save(jpeg, format="JPEG", quality=70)
            jpeg.seek(0)
            c.drawImage(ImageReader(jpeg), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
    c.save()
    return buf.getvalue()


def scanned_text_pdf(pages: tuple[str, ...] = WAREHOUSE_NOTICE, dpi: int = 200) -> bytes:
    """Image-only PDF of known text, degraded like a real scan (no text layer)."""
    return _image_pdf([degrade(img, seed=i) for i, img in enumerate(page_images(pages, dpi))])


def partially_scanned_pdf() -> bytes:
    """Page 1 has a text layer; page 2 is a scanned image."""
    scan = degrade(page_images([WAREHOUSE_NOTICE[1]])[0])
    return _image_pdf([LEAVE_POLICY, scan])


def photo_jpeg(text: str = DELIVERY_NOTE) -> bytes:
    """A phone-photo-like JPEG of a printed note."""
    img = degrade(page_images([text])[0], seed=3)
    width, height = img.size
    img = img.crop((0, 0, width, height // 2))  # the note fills the top half of the page
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def blank_scan_png() -> bytes:
    """A scan with no readable text (only noise)."""
    img = Image.effect_noise((1240, 1754), 30).convert("L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
