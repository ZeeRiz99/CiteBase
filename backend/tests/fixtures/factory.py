"""Generate realistic test documents in memory (no binary fixtures in the repo)."""

from __future__ import annotations

import io
import zipfile

import docx
from reportlab.lib import pdfencrypt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
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
