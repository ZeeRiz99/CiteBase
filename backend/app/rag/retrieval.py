"""Hybrid retrieval: pgvector cosine search + Postgres full-text search, fused with RRF.

Both searches are always restricted to the workspace (explicit filter and RLS), to current
document versions, to live documents, and optionally to permitted collections.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.profiles import EmbeddingProfile

RRF_K = 60


@dataclass
class Candidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    document_title: str
    section_title: str | None
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    chunk_index: int
    text: str
    token_count: int
    file_ext: str
    vector_score: float | None = None
    vector_rank: int | None = None
    keyword_score: float | None = None
    keyword_rank: int | None = None
    fused_score: float = 0.0
    lexemes: list[str] = field(default_factory=list)

    @property
    def location(self) -> str:
        if self.file_ext == ".pdf":
            return (
                f"page {self.page_start}"
                if self.page_start == self.page_end
                else (f"pages {self.page_start}-{self.page_end}")
            )
        return self.section_title or "document"


@dataclass
class RetrievalResult:
    candidates: list[Candidate]  # top-k after fusion, best first
    vector_sims: list[float]  # all vector candidates' similarities (for gate signals)
    query_terms: list[str]
    kw_coverage: float
    kw_hits: int
    timings_ms: dict[str, float]


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def _scope_sql(collection_ids: list[uuid.UUID] | None) -> str:
    return " AND c.collection_id = ANY(:collections)" if collection_ids else ""


_LIVE_JOIN = (
    "JOIN documents d ON d.id = c.document_id "
    "AND d.current_version_id = c.document_version_id AND d.deleted_at IS NULL"
)


async def _vector_search(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    profile: EmbeddingProfile,
    query_vector: list[float],
    limit: int,
    collection_ids: list[uuid.UUID] | None,
) -> list[tuple[uuid.UUID, float]]:
    dim = int(profile.dimension)  # from the code registry, never user input
    # Iterative scans keep filtered HNSW queries from returning too few rows (pgvector >= 0.8).
    await db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    await db.execute(text("SET LOCAL hnsw.ef_search = 100"))
    sql = text(
        f"""
        SELECT c.id, 1 - ((ce.embedding::vector({dim})) <=> CAST(:q AS vector({dim}))) AS sim
        FROM chunk_embeddings ce
        JOIN chunks c ON c.id = ce.chunk_id
        {_LIVE_JOIN}
        WHERE ce.profile_id = :pid AND ce.workspace_id = :ws AND c.workspace_id = :ws
        {_scope_sql(collection_ids)}
        ORDER BY (ce.embedding::vector({dim})) <=> CAST(:q AS vector({dim}))
        LIMIT :limit
        """  # noqa: S608 - only integer dimension interpolated
    )
    params: dict[str, object] = {
        "q": _vector_literal(query_vector),
        "pid": profile.id,
        "ws": workspace_id,
        "limit": limit,
    }
    if collection_ids:
        params["collections"] = collection_ids
    rows = (await db.execute(sql, params)).all()
    # relaxed_order may return results slightly out of order; sort exactly.
    return sorted(((r[0], float(r[1])) for r in rows), key=lambda r: r[1], reverse=True)


async def _keyword_search(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    fts_config: str,
    query_text: str,
    limit: int,
    collection_ids: list[uuid.UUID] | None,
) -> tuple[list[tuple[uuid.UUID, float]], list[str]]:
    terms_row = await db.execute(
        text(
            "SELECT coalesce(array_agg(DISTINCT lexeme), '{}') "
            "FROM unnest(to_tsvector(CAST(:cfg AS regconfig), :q))"
        ),
        {"cfg": fts_config, "q": query_text},
    )
    terms: list[str] = list(terms_row.scalar_one())
    if not terms:
        return [], []
    # OR the query's lexemes: natural-language questions rarely have every term in one chunk.
    sql = text(
        f"""
        SELECT c.id, ts_rank_cd(c.tsv, q.query, 32) AS score
        FROM chunks c
        {_LIVE_JOIN}
        CROSS JOIN (
            SELECT replace(plainto_tsquery(CAST(:cfg AS regconfig), :q)::text, '&', '|')::tsquery
                AS query
        ) q
        WHERE c.workspace_id = :ws AND c.tsv @@ q.query
        {_scope_sql(collection_ids)}
        ORDER BY score DESC
        LIMIT :limit
        """  # noqa: S608 - no user input interpolated
    )
    params: dict[str, object] = {
        "cfg": fts_config,
        "q": query_text,
        "ws": workspace_id,
        "limit": limit,
    }
    if collection_ids:
        params["collections"] = collection_ids
    rows = (await db.execute(sql, params)).all()
    return [(r[0], float(r[1])) for r in rows], terms


async def _details(
    db: AsyncSession, workspace_id: uuid.UUID, ids: list[uuid.UUID]
) -> dict[uuid.UUID, Candidate]:
    rows = await db.execute(
        text(
            """
            SELECT c.id, c.document_id, c.document_version_id, d.title, c.section_title,
                   c.page_start, c.page_end, c.char_start, c.char_end, c.chunk_index, c.text,
                   c.token_count, v.file_ext, coalesce(tsvector_to_array(c.tsv), '{}')
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            JOIN document_versions v ON v.id = c.document_version_id
            WHERE c.workspace_id = :ws AND c.id = ANY(:ids)
            """
        ),
        {"ws": workspace_id, "ids": ids},
    )
    out: dict[uuid.UUID, Candidate] = {}
    for r in rows:
        out[r[0]] = Candidate(
            chunk_id=r[0],
            document_id=r[1],
            document_version_id=r[2],
            document_title=r[3],
            section_title=r[4],
            page_start=r[5],
            page_end=r[6],
            char_start=r[7],
            char_end=r[8],
            chunk_index=r[9],
            text=r[10],
            token_count=r[11],
            file_ext=r[12],
            lexemes=list(r[13]),
        )
    return out


def fuse(
    vector: list[tuple[uuid.UUID, float]], keyword: list[tuple[uuid.UUID, float]]
) -> dict[uuid.UUID, float]:
    """Reciprocal Rank Fusion: score = sum over lists of 1 / (60 + rank)."""
    scores: dict[uuid.UUID, float] = {}
    for results in (vector, keyword):
        for rank, (chunk_id, _score) in enumerate(results, 1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    return scores


async def retrieve(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    profile: EmbeddingProfile,
    query_vector: list[float],
    query_text: str,
    fts_config: str,
    top_k: int,
    candidates: int,
    collection_ids: list[uuid.UUID] | None = None,
) -> RetrievalResult:
    t0 = time.perf_counter()
    vector = await _vector_search(
        db,
        workspace_id=workspace_id,
        profile=profile,
        query_vector=query_vector,
        limit=candidates,
        collection_ids=collection_ids,
    )
    t1 = time.perf_counter()
    keyword, terms = await _keyword_search(
        db,
        workspace_id=workspace_id,
        fts_config=fts_config,
        query_text=query_text,
        limit=candidates,
        collection_ids=collection_ids,
    )
    t2 = time.perf_counter()

    fused = fuse(vector, keyword)
    top_ids = [cid for cid, _ in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]]
    details = await _details(db, workspace_id, top_ids) if top_ids else {}
    v_rank = {cid: (i, s) for i, (cid, s) in enumerate(vector, 1)}
    k_rank = {cid: (i, s) for i, (cid, s) in enumerate(keyword, 1)}
    result: list[Candidate] = []
    for cid in top_ids:
        cand = details.get(cid)
        if cand is None:
            continue
        cand.fused_score = fused[cid]
        if cid in v_rank:
            cand.vector_rank, cand.vector_score = v_rank[cid]
        if cid in k_rank:
            cand.keyword_rank, cand.keyword_score = k_rank[cid]
        result.append(cand)

    covered = set(terms) & {lex for c in result for lex in c.lexemes}
    return RetrievalResult(
        candidates=result,
        vector_sims=[s for _, s in vector],
        query_terms=terms,
        kw_coverage=len(covered) / len(terms) if terms else 0.0,
        kw_hits=len(keyword),
        timings_ms={
            "vector_search": (t1 - t0) * 1000,
            "keyword_search": (t2 - t1) * 1000,
            "fusion_and_fetch": (time.perf_counter() - t2) * 1000,
        },
    )
