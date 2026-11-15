"""Write fictional sample documents for manual testing of uploads (DEMO DATA, not real).

Usage (from the repo root):
    docker compose run --rm --no-deps -u root -v ./samples:/samples api \
        python -m scripts.make_samples /samples
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.fixtures import factory

HANDBOOK_PAGES = [
    "DEMO DATA: fictional company, for testing only.\n\n"
    "Welcome to Northwind Outfitters. This handbook explains how we work, what we expect "
    "from each other and where to find help.",
    factory.LEAVE_POLICY
    + "\n\nSick leave is separate from annual leave. Employees should notify their manager before "
    "9:00 on the first day of absence.",
    "Expenses are reimbursed monthly. Submit receipts within thirty days through the finance "
    "portal. Hotel stays are capped at 150 EUR per night and meals at 40 EUR per day.",
    "Remote work is available up to three days per week with manager approval. Equipment for "
    "home offices is provided once per year.",
]

README = """CiteBase sample documents. DEMO DATA: everything here is fictional.

Northwind Handbook.pdf    4-page PDF with a repeated header and page numbers
Shipping Rates.pdf        PDF with a table (becomes a Markdown table)
Employee Handbook.docx    Word document with headings, a bulleted list and a table
Returns Policy.md         Markdown with sections, a code block and a table
Support Guide.txt         Plain text
Scanned Notice.pdf        Image-only PDF: should be flagged "needs OCR", not indexed
"""


def main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "Northwind Handbook.pdf": factory.pdf_with_text(HANDBOOK_PAGES),
        "Shipping Rates.pdf": factory.pdf_with_table(),
        "Employee Handbook.docx": factory.docx_document(),
        "Returns Policy.md": factory.MARKDOWN.encode(),
        "Support Guide.txt": factory.TEXT.encode(),
        "Scanned Notice.pdf": factory.scanned_pdf(),
        "README.txt": README.encode(),
    }
    for name, data in files.items():
        (target / name).write_bytes(data)
        print(f"wrote {name} ({len(data):,} bytes)")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "samples"))
