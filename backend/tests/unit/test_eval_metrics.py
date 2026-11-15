"""The evaluation harness's own metrics must be correct before their numbers mean anything."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.ingestion.extractors import extract
from app.rag.profiles import GateThresholds
from evals import metrics
from evals.build_corpus import OUT
from evals.metrics import GateSample


def test_quote_matching_ignores_case_punctuation_and_table_pipes() -> None:
    row = "| France | 3-4 business days | 6.90 EUR | 2 business days | 15.90 EUR |"
    assert metrics.is_relevant(row, ["France | 3-4 business days | 6.90 EUR | 2 business days"])
    assert metrics.is_relevant(
        "A doctor’s note is required from the fourth day", ["doctor's note is required"]
    )
    assert not metrics.is_relevant("Price 1159 EUR", ["Price 159 EUR"])  # whole-token match only


def test_first_relevant_rank() -> None:
    passages = ["unrelated", "also unrelated", "Leave: 25 days of paid annual leave per year"]
    assert metrics.first_relevant_rank(passages, ["25 days of paid annual leave"]) == 3
    assert metrics.first_relevant_rank(passages, ["not present"]) is None


def test_gate_calibration_separates_toy_signals() -> None:
    samples = [
        GateSample(f"a{i}", "train", True, v, 0.6) for i, v in enumerate([0.71, 0.74, 0.8, 0.85])
    ]
    samples += [GateSample(f"n{i}", "train", False, v, 0.0) for i, v in enumerate([0.4, 0.45, 0.5])]
    samples += [
        GateSample("h1", "holdout", True, 0.78, 0.5),
        GateSample("h2", "holdout", False, 0.42, 0.0),
    ]
    calibration = metrics.calibrate_gate(samples)
    assert calibration.train == {
        "answerable_pass_rate": 1.0,
        "offtopic_refusal_rate": 1.0,
        "balanced_accuracy": 1.0,
    }
    assert calibration.holdout["balanced_accuracy"] == 1.0
    t = calibration.thresholds
    # Both thresholds sit in the gap between off-topic (<= 0.5) and answerable (>= 0.71) signals,
    # so an off-topic question cannot pass on keywords alone at a low similarity.
    assert 0.5 < t.vec_lo <= t.vec_hi < 0.71


def test_gate_passes_matches_production_rule() -> None:
    t = GateThresholds(vec_hi=0.8, vec_lo=0.6, kw_coverage=0.5)
    assert metrics.gate_passes(GateSample("x", "train", True, 0.81, 0.0), t)
    assert metrics.gate_passes(GateSample("x", "train", True, 0.65, 0.5), t)
    assert not metrics.gate_passes(GateSample("x", "train", True, 0.65, 0.4), t)


def test_golden_set_is_well_formed() -> None:
    golden = yaml.safe_load((Path(__file__).parents[2] / "evals" / "golden.yaml").read_text())[
        "questions"
    ]
    ids = [q["id"] for q in golden]
    assert len(golden) >= 36 and len(ids) == len(set(ids))
    types = {q["type"] for q in golden}
    assert types == {
        "direct",
        "multi_chunk",
        "follow_up",
        "table",
        "unanswerable",
        "near_miss",
        "injection",
    }
    for q in golden:
        assert q["split"] in {"train", "holdout"}
        if q.get("should_refuse"):
            assert not q.get("expected_quotes")
        else:
            assert q["expected_quotes"] and q["key_points"], q["id"]
    holdout = sum(q["split"] == "holdout" for q in golden) / len(golden)
    assert 0.25 <= holdout <= 0.4


def test_expected_quotes_exist_in_the_corpus() -> None:
    """Every label must be findable in the extracted corpus text, or recall is meaningless."""
    corpus = " ".join(
        page.text for path in OUT.iterdir() for page in extract(path, path.suffix.lower()).pages
    )
    golden = yaml.safe_load((Path(__file__).parents[2] / "evals" / "golden.yaml").read_text())[
        "questions"
    ]
    missing = [
        (q["id"], quote)
        for q in golden
        for quote in q.get("expected_quotes", [])
        if not metrics.is_relevant(corpus, [quote])
    ]
    assert missing == []
