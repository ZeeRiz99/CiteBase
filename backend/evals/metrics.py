"""Evaluation metrics. Pure functions over recorded results, so they are unit-testable."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from statistics import quantiles
from typing import Any

from app.rag.profiles import GateThresholds


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def is_relevant(passage: str, quotes: Sequence[str]) -> bool:
    haystack = f" {normalize(passage)} "
    return any(f" {normalize(q)} " in haystack for q in quotes if q.strip())


def first_relevant_rank(passages: Sequence[str], quotes: Sequence[str]) -> int | None:
    for rank, passage in enumerate(passages, 1):
        if is_relevant(passage, quotes):
            return rank
    return None


def percentile(values: Sequence[float], q: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[q - 1]


def rate(flags: Iterable[bool]) -> float | None:
    items = list(flags)
    return sum(items) / len(items) if items else None


@dataclass
class GateSample:
    qid: str
    split: str
    should_pass: bool | None  # None: either is acceptable
    vec_max: float
    kw_coverage: float


@dataclass
class Calibration:
    thresholds: GateThresholds
    train: dict[str, float | None] = field(default_factory=dict)
    holdout: dict[str, float | None] = field(default_factory=dict)
    candidates_tried: int = 0


def gate_passes(sample: GateSample, t: GateThresholds) -> bool:
    if sample.vec_max >= t.vec_hi:
        return True
    return sample.vec_max >= t.vec_lo and sample.kw_coverage >= t.kw_coverage


def gate_scores(samples: Sequence[GateSample], t: GateThresholds) -> dict[str, float | None]:
    labelled = [s for s in samples if s.should_pass is not None]
    pos = [s for s in labelled if s.should_pass]
    neg = [s for s in labelled if not s.should_pass]
    pass_rate = rate(gate_passes(s, t) for s in pos)
    refuse_rate = rate(not gate_passes(s, t) for s in neg)
    balanced = None
    if pass_rate is not None and refuse_rate is not None:
        balanced = (pass_rate + refuse_rate) / 2
    return {
        "answerable_pass_rate": pass_rate,
        "offtopic_refusal_rate": refuse_rate,
        "balanced_accuracy": balanced,
    }


def calibrate_gate(samples: Sequence[GateSample], min_pass_rate: float = 0.95) -> Calibration:
    """Grid-search thresholds on the train split; report both splits.

    Objective: maximise balanced accuracy among settings that pass at least `min_pass_rate` of
    answerable questions (answering is the product; refusing real questions is the worse error).
    Ties prefer, in order: fewer answerable questions that pass only through the keyword branch
    (semantic evidence is the more robust signal), vec_hi in the middle of the gap between
    observed signals (largest margin), then the higher, more conservative vec_lo.
    """
    train = [s for s in samples if s.split == "train"]
    holdout = [s for s in samples if s.split == "holdout"]
    positives = [s for s in train if s.should_pass]
    steps = [round(x * 0.01, 2) for x in range(20, 100)]
    kw_steps = [0.0, 0.25, 0.34, 0.5, 0.67, 0.75, 1.01]
    best: tuple[float, ...] | None = None
    best_t: GateThresholds | None = None
    tried = 0
    signals = sorted({round(s.vec_max, 4) for s in train})
    for hi in steps:
        hi_margin = min((abs(v - hi) for v in signals), default=0.0)
        keyword_only = sum(1 for s in positives if s.vec_max < hi)
        for lo in (x for x in steps if x <= hi):
            for kw in kw_steps:
                tried += 1
                t = GateThresholds(vec_hi=hi, vec_lo=lo, kw_coverage=kw)
                scores = gate_scores(train, t)
                pass_rate = scores["answerable_pass_rate"] or 0.0
                feasible = 1.0 if pass_rate >= min_pass_rate else 0.0
                key = (
                    feasible,
                    scores["balanced_accuracy"] or 0.0,
                    -keyword_only,
                    round(hi_margin, 4),
                    lo,
                )
                if best is None or key > best:
                    best, best_t = key, t
    assert best_t is not None
    return Calibration(
        thresholds=best_t,
        train=gate_scores(train, best_t),
        holdout=gate_scores(holdout, best_t),
        candidates_tried=tried,
    )


def summarize(rows: Sequence[dict[str, Any]], top_k: int) -> dict[str, Any]:
    """Aggregate per-question rows produced by evals.run into report metrics."""
    answerable = [r for r in rows if not r["should_refuse"]]
    ranks = [r["first_relevant_rank"] for r in answerable]
    markers_valid = sum(len(r["cited_numbers"]) for r in rows)
    markers_invalid = sum(len(r["invalid_citations"]) for r in rows)
    cited_total = sum(r["cited_relevant"] + r["cited_irrelevant"] for r in rows)
    refusal_expected = [r for r in rows if r["should_refuse"]]
    refused = [r for r in rows if r["refused"]]
    judged = [r for r in rows if r.get("judge")]
    totals = [r["timings_ms"].get("total", 0.0) for r in rows]
    injection = [r for r in rows if r["type"] == "injection"]
    return {
        "questions": len(rows),
        "recall_at_1": rate((rk is not None and rk <= 1) for rk in ranks),
        "recall_at_3": rate((rk is not None and rk <= 3) for rk in ranks),
        f"recall_at_{top_k}": rate(rk is not None for rk in ranks),
        "mrr": (sum(1 / rk for rk in ranks if rk) / len(ranks)) if ranks else None,
        "raw_citation_validity": (markers_valid / (markers_valid + markers_invalid))
        if (markers_valid + markers_invalid)
        else None,
        "served_citation_validity": 1.0 if markers_valid else None,
        "citation_precision": (sum(r["cited_relevant"] for r in rows) / cited_total)
        if cited_total
        else None,
        "refusal_accuracy": rate(r["refused"] == r["should_refuse"] for r in rows),
        "refusal_recall": rate(r["refused"] for r in refusal_expected),
        "refusal_precision": rate(r["should_refuse"] for r in refused),
        "false_refusals": sum(1 for r in answerable if r["refused"]),
        "gate_refusals": sum(1 for r in rows if r["refusal_reason"] == "gate"),
        "key_point_recall": rate(
            kp for r in judged if not r["should_refuse"] for kp in r["judge"].get("key_points", [])
        ),
        "faithfulness": rate(
            r["judge"].get("faithful") is True for r in judged if not r["refused"]
        ),
        "injection_resistance": rate(
            not (r.get("judge") or {}).get("injection_followed", False) and not r["served_invalid"]
            for r in injection
        ),
        "latency_p50_ms": percentile(totals, 50),
        "latency_p95_ms": percentile(totals, 95),
    }
