"""Relevance gate: decide from retrieval evidence whether to call the LLM at all.

Signals come from the raw searches, never from the fused rank score (RRF scores are not
comparable across questions). Thresholds are per embedding profile and calibrated by the
evaluation harness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Literal

from app.rag.profiles import GateThresholds

Evidence = Literal["strong", "partial", "weak"]


@dataclass(frozen=True)
class GateSignals:
    vec_max: float  # best cosine similarity
    vec_margin: float  # vec_max minus the median similarity of all vector candidates
    n_vec_strong: int  # candidates at or above the profile's vec_hi
    kw_coverage: float  # share of query lexemes found in the top-k chunks
    kw_hits: int  # chunks matching at least one query lexeme
    query_terms: int

    def as_dict(self) -> dict[str, Any]:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in asdict(self).items()}


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    evidence: Evidence
    reason: str


def compute_signals(
    vector_sims: list[float],
    *,
    kw_coverage: float,
    kw_hits: int,
    query_terms: int,
    thresholds: GateThresholds,
) -> GateSignals:
    vec_max = max(vector_sims, default=0.0)
    vec_margin = vec_max - median(vector_sims) if vector_sims else 0.0
    return GateSignals(
        vec_max=vec_max,
        vec_margin=vec_margin,
        n_vec_strong=sum(1 for s in vector_sims if s >= thresholds.vec_hi),
        kw_coverage=kw_coverage,
        kw_hits=kw_hits,
        query_terms=query_terms,
    )


def decide(signals: GateSignals, thresholds: GateThresholds) -> GateDecision:
    keyword_confirms = signals.kw_coverage >= thresholds.kw_coverage
    if signals.vec_max >= thresholds.vec_hi:
        strong = signals.n_vec_strong >= 2 or keyword_confirms
        return GateDecision(True, "strong" if strong else "partial", "high semantic similarity")
    if signals.vec_max >= thresholds.vec_lo and keyword_confirms:
        return GateDecision(True, "partial", "moderate similarity confirmed by keywords")
    return GateDecision(False, "weak", "retrieved passages are not relevant enough")
