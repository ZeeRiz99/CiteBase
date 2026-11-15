"""Embedding profiles: which model produced a vector, and how to use it.

A workspace references one profile. Vectors are stored per (chunk, profile), and each profile
has its own partial HNSW index, so changing a workspace's model re-embeds into new rows instead
of mixing incompatible vectors. Migration 0003 seeds `embedding_profiles` with these rows; a test
keeps the two in sync.

Relevance-gate thresholds are per profile because cosine similarity distributions differ a lot
between models. They are calibrated by the evaluation harness (docs/evals/), never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Provider = Literal["local", "gemini", "openai"]


@dataclass(frozen=True)
class GateThresholds:
    vec_hi: float  # a single chunk this similar is enough evidence on its own
    vec_lo: float  # below this, never answer
    kw_coverage: float  # between lo and hi, require this share of query terms in the top chunks


@dataclass(frozen=True)
class EmbeddingProfile:
    id: int
    key: str
    provider: Provider
    model: str
    dimension: int
    max_input_tokens: int
    query_prefix: str = ""
    passage_prefix: str = ""
    gate: GateThresholds = field(default_factory=lambda: GateThresholds(0.75, 0.55, 0.5))
    gate_calibrated: bool = False  # True once thresholds come from an eval report


PROFILES: dict[int, EmbeddingProfile] = {
    1: EmbeddingProfile(
        id=1,
        key="local-e5-small",
        provider="local",
        model="intfloat/multilingual-e5-small",
        dimension=384,
        max_input_tokens=512,
        query_prefix="query: ",
        passage_prefix="passage: ",
        gate=GateThresholds(vec_hi=0.86, vec_lo=0.80, kw_coverage=0.5),
    ),
    2: EmbeddingProfile(
        id=2,
        key="gemini-embedding-2-768",
        provider="gemini",
        model="gemini-embedding-2",
        dimension=768,
        max_input_tokens=8192,
        gate=GateThresholds(vec_hi=0.75, vec_lo=0.55, kw_coverage=0.5),
    ),
    3: EmbeddingProfile(
        id=3,
        key="openai-3-small",
        provider="openai",
        model="text-embedding-3-small",
        dimension=1536,
        max_input_tokens=8191,
        gate=GateThresholds(vec_hi=0.55, vec_lo=0.35, kw_coverage=0.5),
    ),
}


def get_profile(profile_id: int) -> EmbeddingProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown embedding profile {profile_id}") from exc
