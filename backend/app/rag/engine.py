"""The answering pipeline. One code path serves the CLI, the eval harness and (Phase 4) chat.

question ─▶ standalone query (follow-ups only) ─▶ embed ─▶ hybrid retrieval ─▶ relevance gate
  ├─ weak evidence ─▶ refusal (no LLM call)
  └─ else ─▶ stream answer ─▶ validate citations ─▶ (no valid citation? regenerate once) ─▶ done
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import aclosing
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.providers.embeddings import EmbeddingProvider
from app.providers.http import ProviderError
from app.providers.llm import GenerationParams, LLMMessage, LLMProvider, LLMUsage, complete
from app.rag.citations import CitationCheck, validate
from app.rag.constants import REFUSAL_TEXT
from app.rag.gate import Evidence, GateSignals, compute_signals, decide
from app.rag.profiles import EmbeddingProfile, GateThresholds
from app.rag.prompting import (
    PROMPT_VERSION,
    RETRY_REMINDER,
    STRONG_EVIDENCE_REMINDER,
    SYSTEM_PROMPT,
    PromptSource,
    user_message,
)
from app.rag.retrieval import Candidate, RetrievalResult, retrieve

log = structlog.get_logger("rag")

RefusalReason = Literal["gate", "model", "no_valid_citation"]

REWRITE_SYSTEM = (
    "Rewrite the user's latest question as one standalone question that can be understood "
    "without the conversation. Keep names, numbers and terms exactly. Reply with the question only."
)


@dataclass
class SourceRef:
    number: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    document_title: str
    section_title: str | None
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    location: str
    snippet: str
    vector_score: float | None
    keyword_score: float | None
    fused_score: float
    cited: bool = False


@dataclass
class AnswerResult:
    question: str
    standalone_query: str
    text: str
    refused: bool
    refusal_reason: RefusalReason | None
    evidence: Evidence
    sources: list[SourceRef]
    cited_numbers: list[int]
    invalid_citations: list[int]
    regenerated: bool
    signals: GateSignals
    usage: list[LLMUsage]
    timings_ms: dict[str, float]
    prompt_version: str = PROMPT_VERSION

    @property
    def cited_sources(self) -> list[SourceRef]:
        return [s for s in self.sources if s.cited]

    def trace(self) -> dict[str, Any]:
        """The admin "why this answer?" record: retrieval, gate, tokens, timings."""
        return {
            "standalone_query": self.standalone_query,
            "evidence": self.evidence,
            "refusal_reason": self.refusal_reason,
            "signals": self.signals.as_dict(),
            "sources": [
                {
                    **asdict(s),
                    "chunk_id": str(s.chunk_id),
                    "document_id": str(s.document_id),
                    "document_version_id": str(s.document_version_id),
                    "snippet": s.snippet[:160],
                }
                for s in self.sources
            ],
            "invalid_citations": self.invalid_citations,
            "regenerated": self.regenerated,
            "usage": [asdict(u) for u in self.usage],
            "timings_ms": {k: round(v, 1) for k, v in self.timings_ms.items()},
            "prompt_version": self.prompt_version,
        }


@dataclass
class MetaEvent:
    standalone_query: str
    evidence: Evidence
    sources: list[SourceRef]
    signals: GateSignals
    # Live references, so a caller that stops mid-answer can still record what was spent.
    usage: list[LLMUsage] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


@dataclass
class TokenEvent:
    text: str


@dataclass
class ReplaceEvent:
    text: str  # replaces everything streamed so far (regenerated answer or refusal)


@dataclass
class DoneEvent:
    result: AnswerResult


RagEvent = MetaEvent | TokenEvent | ReplaceEvent | DoneEvent


@dataclass
class EngineConfig:
    top_k: int = 6
    candidates: int = 30
    temperature: float = 0.1
    max_output_tokens: int = 1024
    thresholds: GateThresholds | None = None  # default: the profile's calibrated thresholds
    collection_ids: list[uuid.UUID] | None = None


def _sources(candidates: Sequence[Candidate]) -> list[SourceRef]:
    return [
        SourceRef(
            number=i,
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_version_id=c.document_version_id,
            document_title=c.document_title,
            section_title=c.section_title,
            page_start=c.page_start,
            page_end=c.page_end,
            char_start=c.char_start,
            char_end=c.char_end,
            location=c.location,
            snippet=c.text,
            vector_score=c.vector_score,
            keyword_score=c.keyword_score,
            fused_score=c.fused_score,
        )
        for i, c in enumerate(candidates, 1)
    ]


@dataclass
class RagEngine:
    db: AsyncSession
    workspace_id: uuid.UUID
    fts_config: str
    profile: EmbeddingProfile
    embedder: EmbeddingProvider
    llm: LLMProvider
    cheap_llm: LLMProvider
    config: EngineConfig = field(default_factory=EngineConfig)

    @property
    def thresholds(self) -> GateThresholds:
        return self.config.thresholds or self.profile.gate

    async def standalone_query(
        self, question: str, history: Sequence[LLMMessage], usage: list[LLMUsage]
    ) -> str:
        if not history:
            return question
        transcript = "\n".join(f"{m.role}: {m.content}" for m in history[-6:])
        try:
            result = await complete(
                self.cheap_llm,
                REWRITE_SYSTEM,
                [LLMMessage("user", f"Conversation:\n{transcript}\n\nLatest question: {question}")],
                GenerationParams(temperature=0.0, max_tokens=200),
            )
        except ProviderError as exc:
            log.warning("query_rewrite_failed", error=exc.message)
            return question
        usage.append(replace(result.usage, kind="rewrite"))
        rewritten = result.text.strip().strip('"')
        return rewritten or question

    async def search(self, query: str) -> tuple[RetrievalResult, GateSignals, float]:
        t0 = time.perf_counter()
        [vector] = await self.embedder.embed([query], "query")
        embed_ms = (time.perf_counter() - t0) * 1000
        result = await retrieve(
            self.db,
            workspace_id=self.workspace_id,
            profile=self.profile,
            query_vector=vector,
            query_text=query,
            fts_config=self.fts_config,
            top_k=self.config.top_k,
            candidates=self.config.candidates,
            collection_ids=self.config.collection_ids,
        )
        signals = compute_signals(
            result.vector_sims,
            kw_coverage=result.kw_coverage,
            kw_hits=result.kw_hits,
            query_terms=len(result.query_terms),
            thresholds=self.thresholds,
        )
        return result, signals, embed_ms

    async def stream(
        self, question: str, history: Sequence[LLMMessage] = ()
    ) -> AsyncGenerator[RagEvent, None]:
        t_start = time.perf_counter()
        usage: list[LLMUsage] = []
        timings: dict[str, float] = {}

        t = time.perf_counter()
        query = await self.standalone_query(question, history, usage)
        timings["rewrite"] = (time.perf_counter() - t) * 1000

        retrieval, signals, timings["embed_query"] = await self.search(query)
        timings.update(retrieval.timings_ms)
        decision = decide(signals, self.thresholds)
        sources = _sources(retrieval.candidates)
        yield MetaEvent(
            standalone_query=query,
            evidence=decision.evidence,
            sources=sources,
            signals=signals,
            usage=usage,
            timings_ms=timings,
        )

        def finish(
            text: str,
            check: CitationCheck | None,
            reason: RefusalReason | None,
            regenerated: bool,
        ) -> DoneEvent:
            cited = check.cited if check and reason is None else []
            for s in sources:
                s.cited = s.number in cited
            timings["total"] = (time.perf_counter() - t_start) * 1000
            return DoneEvent(
                AnswerResult(
                    question=question,
                    standalone_query=query,
                    text=text,
                    refused=reason is not None,
                    refusal_reason=reason,
                    evidence=decision.evidence,
                    sources=sources,
                    cited_numbers=cited,
                    invalid_citations=check.invalid if check else [],
                    regenerated=regenerated,
                    signals=signals,
                    usage=usage,
                    timings_ms=timings,
                )
            )

        if not decision.passed or not sources:
            yield TokenEvent(REFUSAL_TEXT)
            yield finish(REFUSAL_TEXT, None, "gate", False)
            return

        prompt_sources = [
            PromptSource(s.number, s.document_title, s.location, s.snippet) for s in sources
        ]
        messages = [LLMMessage("user", user_message(query, prompt_sources))]
        params = GenerationParams(
            temperature=self.config.temperature, max_tokens=self.config.max_output_tokens
        )
        valid = {s.number for s in sources}

        t = time.perf_counter()
        parts: list[str] = []
        # aclosing: when the caller stops (user pressed Stop), the provider stream closes at once.
        async with aclosing(self.llm.stream(SYSTEM_PROMPT, messages, params)) as llm_stream:
            async for chunk in llm_stream:
                if chunk.text:
                    parts.append(chunk.text)
                    yield TokenEvent(chunk.text)
                if chunk.usage:
                    usage.append(chunk.usage)
        timings["generate"] = (time.perf_counter() - t) * 1000
        check = validate("".join(parts), valid)

        if check.cited and not check.is_refusal:
            if check.invalid:
                yield ReplaceEvent(check.text)  # strip citations that point at nothing
            yield finish(check.text, check, None, False)
            return
        if check.is_refusal and decision.evidence != "strong":
            yield finish(REFUSAL_TEXT, check, "model", False)
            return

        # One more attempt. A refusal despite strong evidence (small fast models occasionally
        # refuse answerable questions) gets a "read the sources again" reminder; an answer
        # without valid citations gets a stricter citation reminder. Citations are validated
        # again, so a second refusal or an uncited answer stays a refusal.
        reminder = STRONG_EVIDENCE_REMINDER if check.is_refusal else RETRY_REMINDER
        second = await self._second_attempt(
            messages, "".join(parts), reminder, params, valid, usage, timings
        )
        if second.cited and not second.is_refusal:
            yield ReplaceEvent(second.text)
            yield finish(second.text, second, None, True)
            return
        if not check.is_refusal:
            yield ReplaceEvent(REFUSAL_TEXT)
        reason: RefusalReason = "model" if second.is_refusal else "no_valid_citation"
        yield finish(REFUSAL_TEXT, second, "model" if check.is_refusal else reason, True)

    async def _second_attempt(
        self,
        messages: list[LLMMessage],
        first: str,
        reminder: str,
        params: GenerationParams,
        valid: set[int],
        usage: list[LLMUsage],
        timings: dict[str, float],
    ) -> CitationCheck:
        t = time.perf_counter()
        retry = await complete(
            self.llm,
            SYSTEM_PROMPT,
            [*messages, LLMMessage("assistant", first), LLMMessage("user", reminder)],
            params,
        )
        timings["regenerate"] = (time.perf_counter() - t) * 1000
        usage.append(replace(retry.usage, kind="regenerate"))
        return validate(retry.text, valid)

    async def answer(self, question: str, history: Sequence[LLMMessage] = ()) -> AnswerResult:
        result: AnswerResult | None = None
        async for event in self.stream(question, history):
            if isinstance(event, DoneEvent):
                result = event.result
        assert result is not None
        return result


def engine_config_from(settings: Settings) -> EngineConfig:
    return EngineConfig(
        top_k=settings.rag_top_k,
        candidates=settings.rag_candidates,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
    )
