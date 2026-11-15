from __future__ import annotations

import re
from itertools import pairwise

import pytest

from app.ingestion.chunking import (
    ChunkingConfig,
    PageText,
    chunk_pages,
    count_tokens,
    section_label,
)

SENTENCE = "The quarterly report covers revenue, staffing and customer satisfaction in detail."


def ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def long_page(number: int, sentences: int, heading: tuple[str, ...] = ()) -> PageText:
    paragraphs = []
    for p in range(0, sentences, 5):
        paragraphs.append(
            " ".join(f"Item {number}.{i}: {SENTENCE}" for i in range(p, min(p + 5, sentences)))
        )
    return PageText(number=number, text="\n\n".join(paragraphs), heading_path=heading)


CFG = ChunkingConfig(target_tokens=120, max_tokens=150, overlap_tokens=25, min_tokens=40)


def test_offsets_point_at_the_source_text() -> None:
    pages = [long_page(1, 30), long_page(2, 30)]
    chunks = chunk_pages(pages, CFG)
    assert len(chunks) > 3
    by_number = {p.number: p.text for p in pages}
    for chunk in chunks:
        if chunk.page_start == chunk.page_end:
            source = by_number[chunk.page_start][chunk.char_start : chunk.char_end]
            assert ws(source) == ws(chunk.text)
        else:
            assert ws(chunk.text).startswith(
                ws(by_number[chunk.page_start][chunk.char_start :])[:40]
            )


def test_chunk_sizes_respect_limits() -> None:
    chunks = chunk_pages([long_page(1, 60)], CFG)
    assert all(c.token_count <= CFG.max_tokens for c in chunks)
    assert all(c.token_count >= CFG.min_tokens for c in chunks)
    assert all(c.token_count == count_tokens(c.text) for c in chunks)


def test_consecutive_chunks_overlap_within_a_section() -> None:
    chunks = chunk_pages([long_page(1, 40)], CFG)
    assert len(chunks) > 2
    for a, b in pairwise(chunks):
        last_sentence = re.split(r"(?<=\.)\s+", a.text)[-1]
        assert b.text.startswith(last_sentence)


def test_chunks_never_cross_top_level_headings() -> None:
    pages = [
        long_page(1, 8, ("Leave",)),
        long_page(2, 8, ("Leave", "Carry over")),
        long_page(3, 8, ("Expenses",)),
    ]
    chunks = chunk_pages(pages, CFG)
    for c in chunks:
        tops = {pages[n - 1].heading_path[0] for n in range(c.page_start, c.page_end + 1)}
        assert len(tops) == 1, c
    assert any(c.section_title == "Expenses" for c in chunks)


def test_small_sections_are_merged_until_min_size() -> None:
    pages = [
        PageText(1, "Intro. Short line one.", ("Handbook", "A")),
        PageText(2, "Short line two.", ("Handbook", "B")),
        PageText(3, "Short line three.", ("Handbook", "C")),
    ]
    chunks = chunk_pages(pages, CFG)
    assert len(chunks) == 1
    assert chunks[0].page_start == 1 and chunks[0].page_end == 3


def test_pdf_pages_with_enough_text_get_their_own_chunks() -> None:
    pages = [long_page(1, 3), long_page(2, 3), long_page(3, 3)]  # about 57 tokens each
    chunks = chunk_pages(pages, CFG)
    # 57 tokens is above min_tokens (40), so every page boundary ends a chunk.
    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 1), (2, 2), (3, 3)]


def test_tiny_pdf_pages_still_merge() -> None:
    pages = [PageText(n, f"Page {n} heading only.") for n in range(1, 5)]
    chunks = chunk_pages(pages, CFG)
    assert len(chunks) == 1
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 4)


def test_merged_sections_are_labelled_with_their_range() -> None:
    pages = [
        PageText(1, "Short poles text.", ("Catalog", "Poles")),
        PageText(2, "Short bag text.", ("Catalog", "Sleeping Bag")),
    ]
    [chunk] = chunk_pages(pages, CFG)
    assert chunk.section_title == "Catalog › Poles to Sleeping Bag"


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ([()], None),
        ([("A",), ("A",)], "A"),
        ([("A", "B"), ("A", "B")], "A › B"),
        ([("A", "B"), ("A", "C"), ("A", "D")], "A › B to D"),
        ([("A",), ("A", "B")], "A"),
    ],
)
def test_section_label(paths: list[tuple[str, ...]], expected: str | None) -> None:
    assert section_label(paths) == expected


def test_table_chunks_repeat_the_header() -> None:
    header = "| Region | Days | Price |\n| --- | --- | --- |"
    rows = "\n".join(
        f"| Region {i} with a long descriptive name | {i} | {i}.90 EUR |" for i in range(60)
    )
    chunks = chunk_pages([PageText(1, f"{header}\n{rows}")], CFG)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.startswith("| Region | Days | Price |")


def test_overlong_sentence_is_split_by_words() -> None:
    sentence = " ".join(f"word{i}" for i in range(800)) + "."
    chunks = chunk_pages([PageText(1, sentence)], CFG)
    assert len(chunks) > 1
    assert all(c.token_count <= CFG.max_tokens for c in chunks)


def test_closing_quotes_stay_with_their_sentence() -> None:
    text = 'The manager said "approve it." Then the request was filed. ' * 30
    chunks = chunk_pages([PageText(1, text)], CFG)
    assert all('"approve it."' in c.text or "approve it" not in c.text for c in chunks)


def test_chunking_is_deterministic() -> None:
    pages = [long_page(1, 25), long_page(2, 25)]
    assert chunk_pages(pages, CFG) == chunk_pages(pages, CFG)


def test_invalid_config_is_rejected() -> None:
    with pytest.raises(ValueError):
        ChunkingConfig(target_tokens=100, max_tokens=50)
    with pytest.raises(ValueError):
        ChunkingConfig(overlap_tokens=500)
