# CiteBase: progress log

## Current status

**Phase 3 (RAG engine and evals): complete on branch `phase-3/rag-engine`, awaiting approval.** Phases 1 and 2 are closed (tags `phase-1`, `phase-2`). Next: Phase 4 (chat and source viewer).

## Completed

| Date | Phase | What |
|---|---|---|
| 2026-11-14 | 0 | Environment inspected; architecture proposal (`docs/ARCHITECTURE.md`); `CLAUDE.md`; git repo |
| 2026-11-14 | 1 | Docker Engine in WSL; Compose stack; config; structured logging; error envelope; migration 0001 with RLS; full auth; CSRF; rate limiting; audit log; outbox; DB job queue and worker; design tokens; landing skeleton; auth screens; app shell; dashboard; settings; CI |
| 2026-11-15 | 2 | Documents: upload validation, isolated extraction, structure-aware chunking, keyword index, versions, delete and purge, knowledge base UI, sample documents |
| 2026-11-15 | 3 | Migration 0003 (embedding profiles, per-profile vectors with partial HNSW indexes, RLS); provider layer (Gemini live-verified; OpenAI and Anthropic contract-tested; retries and fallback; fake providers for tests); embedding stage in ingestion with a content-hash cache; local embedder service (multilingual-e5-small, ONNX, optional Compose profile); hybrid retrieval (pgvector + OR full-text, RRF, iterative HNSW scans); relevance gate with per-profile calibrated thresholds; versioned prompts with escaped, untrusted sources; server-side citation validation, regenerate-once, refusal detection; follow-up rewriting; `ask` and `reindex` CLI; evaluation harness (fictional 5-document corpus incl. a prompt-injection file, 39 quote-anchored golden questions with train/holdout split, gate calibration, LLM judge, Markdown/JSON/CSV reports, comparison table) |

## Phase 3 verification evidence

- Backend: ruff and mypy strict clean, `alembic check` no drift, **142 pytest tests pass** (49 new: citations, gate, prompt escaping, fusion, fake embeddings, three provider adapters with retry and fallback, embedding storage, retrieval, gate refusal without an LLM call, invalid-citation stripping, regenerate-once, follow-ups, workspace isolation in retrieval, current-version-only retrieval, prompt injection, profile registry vs database, local embedder pooling, eval metrics and golden-set integrity). `pip-audit` (all groups): no known vulnerabilities.
- **Evaluation** (`docs/evals/README.md`, real Gemini calls, 39 questions):

  | Config | Recall@1 | Refusal accuracy | Citation precision | Faithfulness | Injection resistance | p50 |
  |---|---|---|---|---|---|---|
  | baseline (Gemini embeddings, 400-token chunks) | 100% | 100% | 100% | 100% | 100% | 1.4 s |
  | chunk-200 | 92.9% | 100% | 97.1% | 96.4% | 100% | 1.3 s |
  | local-e5 (CPU embeddings, no API cost) | 100% | 97.4% (1 false refusal) | 100% | 100% | 100% | 0.9 s |

  About USD 0.03 per full run on `gemini-3.5-flash-lite`. The demo corpus is small (10 chunks), so retrieval metrics are lenient; see each report's Limitations section.
- Live production path: recreated worker embedded real uploads with Gemini; `python -m app.cli ask` answered with a valid citation and refused an off-topic question at the gate.

## Assumptions in force

1. Repo lives at `D:\Projects\citebase`; dev containers poll for file changes.
2. English-first keyword search (configurable per workspace).
3. One deployment per client; branding through `.env` and web build arguments.
4. Gemini is the default provider (key in the gitignored root `.env`); OpenAI/Anthropic adapters are ready but unverified live.

## Known issues

All known limits are collected per phase in [`docs/BACKLOG.md`](BACKLOG.md) and are handled after the last build phase, as agreed.

## Next step

**Phase 4, chat and source viewer:** conversations, messages and message_sources tables; SSE chat endpoint on the RagEngine stream (meta, token, replace, citations, refusal, done); usage events and per-workspace token limits; unanswered-questions log; feedback; suggested questions; three-pane chat UI with citation chips, hover previews, evidence badge, stop and regenerate; PDF source viewer with passage highlighting; "why this answer?" trace for admins; dashboard question counts; Playwright golden-path smoke test.
