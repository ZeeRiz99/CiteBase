"""Print what the extractors produce for each corpus file (used to write quote-anchored labels)."""

from __future__ import annotations

from app.ingestion.chunking import ChunkingConfig, PageText, chunk_pages
from app.ingestion.extractors import extract
from evals.build_corpus import OUT

for path in sorted(OUT.iterdir()):
    result = extract(path, path.suffix.lower())
    pages = [PageText(p.number, p.text, p.heading_path) for p in result.pages]
    chunks = chunk_pages(pages, ChunkingConfig())
    print(
        f"\n===== {path.name}: {len(result.pages)} pages/sections, {len(chunks)} chunks, ocr={result.needs_ocr}"
    )
    for page in result.pages:
        print(f"--- page {page.number} {page.heading_label or ''}")
        print(page.text)
