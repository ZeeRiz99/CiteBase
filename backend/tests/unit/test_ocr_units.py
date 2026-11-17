from __future__ import annotations

from app.ingestion.ocr import parse_tsv

HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
)


def row(block: int, par: int, line: int, word: int, text: str, conf: float = 95.0) -> str:
    return f"5\t1\t{block}\t{par}\t{line}\t{word}\t0\t0\t10\t10\t{conf}\t{text}"


def test_paragraphs_lines_and_hyphenation() -> None:
    tsv = "\n".join(
        [
            HEADER,
            "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t",  # page row, ignored
            row(1, 1, 1, 1, "Returns"),
            row(1, 1, 1, 2, "are"),
            row(1, 1, 1, 3, "accep-"),
            row(1, 1, 2, 1, "ted", 85.0),
            row(1, 1, 2, 2, "daily."),
            row(2, 1, 1, 1, "Second"),
            row(2, 1, 1, 2, "paragraph.", 75.0),
            "4\t1\t2\t1\t2\t0\t0\t0\t10\t10\t-1\t",  # line row, ignored
            row(2, 1, 2, 1, "   "),  # empty word, ignored
        ]
    )
    result = parse_tsv(tsv)
    assert result.text == "Returns are accepted daily.\n\nSecond paragraph."
    assert result.words == 7
    assert abs((result.confidence or 0) - (95 * 5 + 85 + 75) / 7) < 1e-9


def test_no_words() -> None:
    result = parse_tsv(HEADER + "\n")
    assert result.text == "" and result.confidence is None and result.words == 0


def test_capitalised_word_after_hyphen_is_not_joined() -> None:
    tsv = "\n".join([HEADER, row(1, 1, 1, 1, "Leeds-"), row(1, 1, 2, 1, "Bradford")])
    assert parse_tsv(tsv).text == "Leeds- Bradford"
