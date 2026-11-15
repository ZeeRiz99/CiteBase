"""Structure-aware chunking with exact source offsets.

1. Each page/section is split into blocks (blank-line separated), then into *pieces*:
   table rows, list lines, or sentences. Over-long pieces are split by words.
2. Pieces are packed greedily up to the target size. A chunk ends early at a section start once
   it has reached the minimum size, and always at a change of top-level heading.
3. Consecutive chunks in the same section share an overlap of trailing pieces.
4. A tiny final fragment is merged into the previous chunk when it fits.

Every piece keeps (page, char_start, char_end) into the page text, so citations can point at
the exact passage. A chunk that starts inside a table repeats the table's header rows.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from app.ingestion.extractors.base import HEADING_SEPARATOR


@dataclass(frozen=True)
class ChunkingConfig:
    target_tokens: int = 400
    max_tokens: int = 480
    overlap_tokens: int = 60
    min_tokens: int = 100

    def __post_init__(self) -> None:
        if not 0 < self.min_tokens <= self.target_tokens <= self.max_tokens:
            raise ValueError("require 0 < min_tokens <= target_tokens <= max_tokens")
        if not 0 <= self.overlap_tokens < self.target_tokens:
            raise ValueError("require 0 <= overlap_tokens < target_tokens")

    def as_dict(self) -> dict[str, int | str]:
        return {
            "target_tokens": self.target_tokens,
            "max_tokens": self.max_tokens,
            "overlap_tokens": self.overlap_tokens,
            "min_tokens": self.min_tokens,
            "tokenizer": "cl100k_base",
        }


@dataclass(frozen=True)
class PageText:
    number: int
    text: str
    heading_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkDraft:
    index: int
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    section_title: str | None
    token_count: int
    content_hash: str


@dataclass
class _Piece:
    page: int
    start: int
    end: int
    text: str
    tokens: int
    block: tuple[int, int]  # (page number, block index within the page)
    heading_path: tuple[str, ...]
    starts_section: bool = False
    table_header: str | None = None  # set on table body rows
    kind: str = "prose"  # prose | line | row


@lru_cache(maxsize=1)
def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text, disallowed_special=()))


_BLOCK_SPLIT = re.compile(r"\n[ \t]*\n")
# Whitespace after sentence-ending punctuation (optionally followed by a closing quote or
# bracket, which stays with its sentence) and before a capital letter or digit.
_SENTENCE_END = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"')\]]))\s+(?=[\"'(\[]?[A-Z0-9])")
_LIST_LINE = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+")


def _spans(text: str, pattern: re.Pattern[str], base: int) -> list[tuple[int, int]]:
    """Split text by a separator pattern, returning absolute (start, end) spans of the parts."""
    out: list[tuple[int, int]] = []
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            out.append((base + pos, base + match.start()))
        pos = match.end()
    if pos < len(text):
        out.append((base + pos, base + len(text)))
    return out


def _word_windows(page_text: str, start: int, end: int, max_tokens: int) -> list[tuple[int, int]]:
    """Split an over-long span into windows of whole words under max_tokens."""
    words = [
        (m.start() + start, m.end() + start) for m in re.finditer(r"\S+", page_text[start:end])
    ]
    windows: list[tuple[int, int]] = []
    i = 0
    while i < len(words):
        j = i
        # Grow the window word by word; tokens per word are small, so this is cheap enough.
        while (
            j + 1 < len(words)
            and count_tokens(page_text[words[i][0] : words[j + 1][1]]) <= max_tokens
        ):
            j += 1
        windows.append((words[i][0], words[j][1]))
        i = j + 1
    return windows


def _pieces_for_page(page: PageText, cfg: ChunkingConfig, first: bool) -> list[_Piece]:
    text = page.text
    pieces: list[_Piece] = []
    for b, (bs, be) in enumerate(_spans(text, _BLOCK_SPLIT, 0)):
        block_text = text[bs:be]
        lines = block_text.split("\n")
        block_id = (page.number, b)

        def add(
            start: int,
            end: int,
            kind: str,
            header: str | None = None,
            _bid: tuple[int, int] = block_id,
        ) -> None:
            raw = text[start:end]
            stripped = raw.strip()
            if not stripped:
                return
            lead = len(raw) - len(raw.lstrip())
            start += lead
            end = start + len(stripped)
            tokens = count_tokens(stripped)
            if tokens > cfg.max_tokens:
                for ws, we in _word_windows(text, start, end, cfg.max_tokens):
                    pieces.append(
                        _Piece(
                            page.number,
                            ws,
                            we,
                            text[ws:we],
                            count_tokens(text[ws:we]),
                            _bid,
                            page.heading_path,
                            table_header=header,
                            kind=kind,
                        )
                    )
            else:
                pieces.append(
                    _Piece(
                        page.number,
                        start,
                        end,
                        stripped,
                        tokens,
                        _bid,
                        page.heading_path,
                        table_header=header,
                        kind=kind,
                    )
                )

        if all(line.lstrip().startswith("|") for line in lines if line.strip()) and len(lines) >= 2:
            header = "\n".join(lines[:2]) if re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[1]) else None
            offset = bs
            for i, line in enumerate(lines):
                kind_header = header if (header and i >= 2) else None
                add(offset, offset + len(line), "row", kind_header)
                offset += len(line) + 1
        elif (
            len(lines) > 1 and sum(bool(_LIST_LINE.match(line)) for line in lines) >= len(lines) / 2
        ):
            offset = bs
            for line in lines:
                add(offset, offset + len(line), "line")
                offset += len(line) + 1
        else:
            for ss, se in _spans(block_text, _SENTENCE_END, bs):
                add(ss, se, "prose")
    if pieces and first:
        pieces[0].starts_section = True
    return pieces


def _top(path: tuple[str, ...]) -> str | None:
    return path[0] if path else None


def _render(pieces: list[_Piece]) -> str:
    parts: list[str] = []
    first = pieces[0]
    if first.kind == "row" and first.table_header:
        parts.append(first.table_header + "\n")
    for prev, piece in zip([None, *pieces[:-1]], pieces, strict=False):
        if prev is None:
            parts.append(piece.text)
        elif piece.block == prev.block:
            parts.append(("\n" if piece.kind in ("row", "line") else " ") + piece.text)
        else:
            parts.append("\n\n" + piece.text)
    return "".join(parts)


def _draft(index: int, pieces: list[_Piece]) -> ChunkDraft:
    text = _render(pieces)
    return ChunkDraft(
        index=index,
        text=text,
        page_start=pieces[0].page,
        page_end=pieces[-1].page,
        char_start=pieces[0].start,
        char_end=pieces[-1].end,
        section_title=HEADING_SEPARATOR.join(pieces[0].heading_path) or None,
        token_count=count_tokens(text),
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )


def _size(items: list[_Piece]) -> int:
    return sum(p.tokens for p in items)


def _collect_pieces(pages: list[PageText], cfg: ChunkingConfig) -> list[_Piece]:
    """Split all pages into pieces and mark soft boundaries.

    A soft boundary is a change of heading path (DOCX/MD sections), or every new page for
    documents without headings (PDF/TXT), so a citation can name a single page when the page
    holds enough text. Tiny pages or sections still merge up to min_tokens.
    """
    pieces: list[_Piece] = []
    previous_path: tuple[str, ...] | None = None
    for page in pages:
        boundary = (
            previous_path is None or page.heading_path != previous_path
            if page.heading_path
            else True
        )
        pieces.extend(_pieces_for_page(page, cfg, first=boundary))
        previous_path = page.heading_path
    return pieces


def _overlap_tail(current: list[_Piece], cfg: ChunkingConfig, incoming: _Piece) -> list[_Piece]:
    """Trailing pieces of the previous chunk to repeat at the start of the next one."""
    tail: list[_Piece] = []
    for prev in reversed(current[1:]):  # never repeat the whole chunk
        if _size(tail) + prev.tokens > cfg.overlap_tokens:
            break
        tail.insert(0, prev)
    return [] if _size(tail) + incoming.tokens > cfg.max_tokens else tail


def _group(pieces: list[_Piece], cfg: ChunkingConfig) -> list[list[_Piece]]:
    groups: list[list[_Piece]] = []
    current: list[_Piece] = []
    for piece in pieces:
        if current:
            hard = _top(piece.heading_path) != _top(current[-1].heading_path)
            soft = piece.starts_section and _size(current) >= cfg.min_tokens
            full = _size(current) + piece.tokens > cfg.target_tokens
            if hard or soft or full:
                groups.append(current)
                same_section = full and not hard and not piece.starts_section
                current = (
                    _overlap_tail(current, cfg, piece)
                    if same_section and cfg.overlap_tokens
                    else []
                )
        current.append(piece)
    if current:
        groups.append(current)
    return groups


def _merge_small_tails(groups: list[list[_Piece]], cfg: ChunkingConfig) -> list[list[_Piece]]:
    """Merge a tiny trailing fragment of a section into the chunk before it, when it fits."""
    merged: list[list[_Piece]] = []
    for group in groups:
        if (
            merged
            and _size(group) < cfg.min_tokens
            and _top(group[0].heading_path) == _top(merged[-1][-1].heading_path)
        ):
            fresh = [p for p in group if p not in merged[-1]]
            if _size(merged[-1]) + _size(fresh) <= cfg.max_tokens:
                merged[-1] = merged[-1] + fresh
                continue
        merged.append(group)
    return merged


def chunk_pages(pages: list[PageText], cfg: ChunkingConfig | None = None) -> list[ChunkDraft]:
    cfg = cfg or ChunkingConfig()
    groups = _merge_small_tails(_group(_collect_pieces(pages, cfg), cfg), cfg)
    return [_draft(i, group) for i, group in enumerate(groups)]
