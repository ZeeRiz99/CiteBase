# CiteBase: project memory

Business knowledge-base RAG SaaS: upload documents, ask questions, get answers with verifiable citations, honest refusal.
Product name, tagline, logo and colors come from config (`PRODUCT_NAME`, branding settings), never hardcoded.
Full design: `docs/ARCHITECTURE.md`. Status and next step: `docs/PROGRESS.md`. **Re-read both at the start of every session.**

## Working rules (standing)

- **Gated phases.** Never start a phase before the user approves it. Each phase ends with working, tested, committed code, a short summary, files touched, test output, manual verification commands, and an update to PROGRESS.md and this file. Then stop.
- **Inspect before writing.** Check the environment and existing files first. Never overwrite or delete work without saying why.
- **Evidence over claims.** Never say something works without running it and seeing the output. Find the root cause before changing code. No fake integrations. Demo data only from the labeled seed script.
- **Verify dependencies.** Check current versions and docs before pinning (Next.js, shadcn/ui, pgvector clients, provider SDKs change fast). Every new dependency gets a one-line reason in the PR or commit.
- **Small changes.** No unrelated refactors. Focused files. Business logic out of route handlers. Everything typed.
- **At most one clarifying question**, and only if it changes the architecture; otherwise decide and state the assumption.
- **Honest positioning.** No fake logos, testimonials or invented metrics. Pricing labeled illustrative. Benchmarks only from the eval harness.
- Commit messages end with the attribution line from the session reminder.

## Environment (2026-11-14)

- Windows 11, PowerShell 5.1; **7.8 GB RAM**, i5-8365U, no GPU. Keep the stack lean.
- WSL2 Ubuntu 26.04 (user `dell`). Native Postgres 18 runs in WSL on :5432; leave it alone. **Compose Postgres uses host port 5433.**
- Docker Engine to be installed inside WSL (not Docker Desktop). Containers use Python 3.12. Host Node 24.

## Architecture decisions (approved list grows at each gate)

- **Services:** caddy (single origin :8080, `/api` to api) · web (Next.js) · api (FastAPI) · worker (DB job queue) · embedder (local model, Compose profile `local-embeddings`) · postgres (`pgvector/pgvector:pg17`) · mailpit (dev).
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, uv, ruff, mypy, pytest.
- **Frontend:** Next.js App Router, TS, Tailwind, shadcn/ui, Lucide, Recharts, RHF and Zod, TanStack Query, react-pdf.
- **No LangChain or LlamaIndex.** Own extractors (pdfplumber, pypdfium2, python-docx, markdown-it-py) and own structure-aware splitter.
- **No AGPL dependencies** (no PyMuPDF). Licenses recorded in `docs/THIRD_PARTY.md`.
- **Embeddings:** provider interface. Default local model `intfloat/multilingual-e5-small` (MIT, 384d, 512-token cap); bge-m3 optional on bigger servers. Profiles live in the `embedding_profiles` table; the workspace references one. Vectors live in `chunk_embeddings(chunk_id, profile_id)` with one partial HNSW index per profile. A model change means blue/green re-embed, never mixed vectors.
- **LLM:** one interface with Gemini, OpenAI, Anthropic and fake adapters. Model names in config only. Separate cheap model for rewriting and suggestions.
- **Jobs:** `ingestion_jobs` claimed with `FOR UPDATE SKIP LOCKED`, LISTEN/NOTIFY wake-up, heartbeats, backoff. Redis in V2.
- **Events:** transactional outbox `domain_events` (document.indexed, document.failed, question.unanswered, feedback.received). V3 webhooks consume it.
- **Storage:** interface; local disk now, S3/MinIO in V2. Random storage keys.

## Multi-tenancy and security (non-negotiable)

- Every tenant table has `workspace_id`. Repositories scope every query. Workspace, role and document access are resolved on the server from the session, never from client input. A cross-workspace id returns 404.
- **RLS on:** app role `citebase_app` (non-owner, FORCE RLS). Each request runs in a transaction with `SET LOCAL app.workspace_id` / `app.user_id`. Fails closed.
- Isolation tests are mandatory for every endpoint: a workspace B user can never see, retrieve or cite workspace A data.
- Argon2id; access JWT 15 min plus rotating refresh token (hashed, reuse detection) in httpOnly cookies; double-submit CSRF; rate limits on auth, chat and upload.
- Uploads: allow-list, magic bytes, size and page caps, worker parse with timeout, never execute.
- Provider keys AES-GCM encrypted, never sent to the browser (`last4` only). Logs redact secrets. No stack traces to users.
- Audit log for sensitive actions. pip-audit, npm audit and gitleaks in CI.

## RAG rules

- Pipeline lives in `backend/app/rag/` as explicit, testable modules.
- Hybrid retrieval: vector top 30 (`hnsw.iterative_scan = relaxed_order`) plus keyword top 30 (OR-joined lexemes, `ts_rank_cd`), RRF k=60, top k=6, neighbor expansion. Filters: workspace, permitted collections, **current version only** (join on `documents.current_version_id`), not deleted.
- **Relevance gate before the LLM**, using signals (`vec_max`, `vec_margin`, `n_vec_strong`, `kw_coverage`), **thresholds per embedding profile, calibrated by the eval harness, never guessed**.
- Evidence strength (strong, partial, weak) comes from retrieval signals. Never ask the model for confidence.
- Sources go in `<source id=n>` blocks, framed as untrusted data, with tags escaped. The model has no tools.
- Streaming is text with `[n]` markers. The server validates markers against the sources sent, strips invalid ones, and regenerates once if there is no valid citation and no refusal (`replace` SSE event), otherwise refuses.
- Refusal text (exact): "I couldn't find sufficient information in your uploaded documents to answer this question reliably." Every refusal is logged to `unanswered_questions`.
- SSE events: meta, token, replace, citations, refusal, error, done.
- Chunking: structure-aware. e5-small: target 400 / max 480 / overlap 60; API profiles: 650 / 800 / 80; min 100. Check against the embedding tokenizer to prevent truncation.
- Scanned or empty PDFs become `needs_ocr`, never indexed empty.
- `prompt_version` is stored on messages and in eval reports.

## Evaluation and tests

- `backend/evals/`: fictional corpus (stamped DEMO DATA) including a prompt-injection document; golden set of at least 36 questions with quote-anchored labels and a train/hold-out split.
- `make eval CONFIG=<name>` writes `docs/evals/<date>-<name>.md`. Only harness-produced numbers appear in the README.
- pytest against real Postgres with pgvector, using fake LLM and fake embedder. Vitest for components. One Playwright golden-path smoke test.
- A feature is not done without a test and a manual verification step.

## Scope guard

V1 only until V1 is tagged. V2 (teams, reranker, analytics, widget, S3, Redis, dark mode) and V3 (webhooks, n8n, Drive, notifications, escalation, billing) are designed for but not built early.
