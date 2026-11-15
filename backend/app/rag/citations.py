"""Server-side citation validation: every [n] must point to a source that was actually retrieved."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.constants import REFUSAL_TEXT

_MARKER = re.compile(r"\[\s*(\d+(?:\s*[,;]\s*\d+)*)\s*\]")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?])")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


@dataclass(frozen=True)
class CitationCheck:
    text: str  # with invalid markers removed
    cited: list[int]  # valid source numbers, in order of first use
    invalid: list[int]  # numbers that did not map to a retrieved source
    is_refusal: bool


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


_REFUSAL_NORMALIZED = _normalize(REFUSAL_TEXT)


def is_refusal(text: str) -> bool:
    """True when the reply is the refusal sentence (allowing small punctuation/quote variations)."""
    normalized = _normalize(text)
    return _REFUSAL_NORMALIZED in normalized and len(normalized) <= len(_REFUSAL_NORMALIZED) + 20


def validate(text: str, valid_numbers: set[int]) -> CitationCheck:
    cited: list[int] = []
    invalid: list[int] = []

    def replace(match: re.Match[str]) -> str:
        numbers = [int(n) for n in re.split(r"\s*[,;]\s*", match.group(1))]
        keep = [n for n in numbers if n in valid_numbers]
        invalid.extend(n for n in numbers if n not in valid_numbers)
        for n in keep:
            if n not in cited:
                cited.append(n)
        return "".join(f"[{n}]" for n in keep)

    cleaned = _MARKER.sub(replace, text)
    cleaned = _MULTI_SPACE.sub(" ", _SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)).strip()
    return CitationCheck(text=cleaned, cited=cited, invalid=invalid, is_refusal=is_refusal(cleaned))
