"""Generate the evaluation corpus files (DEMO DATA) into evals/corpus/.

python -m evals.build_corpus
"""

from __future__ import annotations

import io
from pathlib import Path

import docx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

from evals import corpus_content as c

OUT = Path(__file__).parent / "corpus"


def _pdf(path: Path, story: list[object], header: str) -> None:
    def decorate(canvas, doc):  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, header)
        canvas.drawString(A4[0] / 2, 1 * cm, f"Page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4).build(story, onFirstPage=decorate, onLaterPages=decorate)
    path.write_bytes(buf.getvalue())


def _sections_story(sections: list[tuple[str, list[str]]], per_page: int) -> list[object]:
    styles = getSampleStyleSheet()
    story: list[object] = []
    for i, (heading, paragraphs) in enumerate(sections):
        if i and i % per_page == 0:
            story.append(PageBreak())
        story.append(Paragraph(heading, styles["Heading2"]))
        for para in paragraphs:
            story.append(Paragraph(para, styles["BodyText"]))
            story.append(Spacer(1, 0.3 * cm))
    return story


def _table(rows: list[list[str]]) -> Table:
    table = Table(rows)
    table.setStyle([("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)), ("FONTSIZE", (0, 0), (-1, -1), 8)])
    return table


def build() -> list[Path]:
    OUT.mkdir(exist_ok=True)
    styles = getSampleStyleSheet()
    written: list[Path] = []

    path = OUT / "Larkspur Employee Handbook.pdf"
    _pdf(path, _sections_story(c.HANDBOOK, per_page=2), "Larkspur Outfitters - Employee Handbook")
    written.append(path)

    path = OUT / "Larkspur Customer Policies.pdf"
    _pdf(path, _sections_story(c.POLICIES, per_page=3), "Larkspur Outfitters - Customer Policies")
    written.append(path)

    story: list[object] = [
        Paragraph("Shipping and pricing", styles["Heading2"]),
        Paragraph(c.SHIPPING_NOTES[0], styles["BodyText"]),
        Spacer(1, 0.3 * cm),
        Paragraph("Delivery times and prices by country:", styles["BodyText"]),
        Spacer(1, 0.2 * cm),
        _table(c.SHIPPING_TABLE),
        Spacer(1, 0.4 * cm),
        *[Paragraph(n, styles["BodyText"]) for n in c.SHIPPING_NOTES[1:]],
        PageBreak(),
        Paragraph("Business volume discounts", styles["Heading2"]),
        _table(c.VOLUME_TABLE),
        Spacer(1, 0.4 * cm),
        Paragraph("Membership tiers", styles["Heading2"]),
        _table(c.MEMBERSHIP_TABLE),
    ]
    path = OUT / "Larkspur Shipping and Pricing.pdf"
    _pdf(path, story, "Larkspur Outfitters - Shipping and Pricing")
    written.append(path)

    d = docx.Document()
    d.add_heading("Larkspur Product Catalog", level=1)
    d.add_paragraph(c.DEMO)
    for product in c.PRODUCTS:
        d.add_heading(product["name"], level=2)
        d.add_paragraph(f"SKU {product['sku']}. Price {product['price']}. {product['details']}")
        d.add_paragraph(f"Warranty: {product['warranty']}.")
        if product["sku"] == "LK-JKT-310":
            d.add_paragraph("Size guide for the Alpine Down Jacket:")
            table = d.add_table(rows=len(c.JACKET_SIZES), cols=3)
            for r, row in enumerate(c.JACKET_SIZES):
                for col, value in enumerate(row):
                    table.cell(r, col).text = value
    d.add_heading("Warranty claims", level=2)
    for para in c.WARRANTY_TEXT:
        d.add_paragraph(para)
    path = OUT / "Larkspur Product Catalog.docx"
    buf = io.BytesIO()
    d.save(buf)
    path.write_bytes(buf.getvalue())
    written.append(path)

    story = [
        Paragraph("Gift cards", styles["Heading2"]),
        Paragraph(c.DEMO, styles["BodyText"]),
        Spacer(1, 0.3 * cm),
        Paragraph(c.GIFT_CARD_NOTE, styles["BodyText"]),
        Spacer(1, 0.2 * cm),
        _table(c.GIFT_CARD_TABLE),
    ]
    path = OUT / "Larkspur Gift Cards.pdf"
    _pdf(path, story, "Larkspur Outfitters - Gift Cards")
    written.append(path)

    path = OUT / "Larkspur Supplier Notes.md"
    path.write_text(c.SUPPLIER_NOTES, encoding="utf-8")
    written.append(path)
    return written


if __name__ == "__main__":
    for p in build():
        print(f"wrote {p.name} ({p.stat().st_size:,} bytes)")
