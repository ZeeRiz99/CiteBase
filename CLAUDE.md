# CiteBase: project memory

Business knowledge-base RAG SaaS: upload documents, ask questions, get answers with verifiable citations, honest refusal.
Product name, tagline, logo and colors come from config (`PRODUCT_NAME`, branding settings), never hardcoded.
Full design: `docs/ARCHITECTURE.md`. Status and next step: `docs/PROGRESS.md`. **Re-read both at the start of every session.**

## Working rules (standing)

- **Gated phases.** Never start a phase before the user approves it. Each phase ends with working, tested, committed code, a short summary, files touched, test output, manual verification commands, and an update to PROGRESS.md and this file. Then stop.
- **Known limits go to `docs/BACKLOG.md`** (one section per phase) and are fixed together after the last build phase, per the user (2026-11-15). Do not fix them mid-phase.
- **Secrets never in chat or git.** API keys go in the gitignored root `.env`; code reads them from the environment.
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
- Docker Engine 29 + Compose 2.40 installed inside WSL (not Docker Desktop); `.wslconfig` gives WSL 5 GB. Containers use Python 3.12 and Node 24.
- (2026-11-16) The WSL disk lives at `D:\WSL\Ubuntu\ext4.vhdx` (moved from C: with `wsl --manage Ubuntu --move` after a build filled C: to 0 bytes and crashed WSL). Watch free space on both drives before large builds; `docker builder prune -f` clears the build cache.
- Repo lives at `D:\Projects\citebase` (WSL path `/mnt/d/Projects/citebase`), where the user keeps all projects; dev containers use polling file watchers.
- Assumed (user did not answer Phase 0 questions): English-first FTS, one deployment per client (branding via env and build args), no LLM keys needed until Phase 3.

## Architecture decisions (approved list grows at each gate)

- **Services:** caddy (single origin :8080, `/api` to api) · web (Next.js) · api (FastAPI) · worker (DB job queue) · embedder (local model, Compose profile `local-embeddings`) · postgres (`pgvector/pgvector:pg17`) · mailpit (dev).
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, uv, ruff, mypy, pytest.
- **Frontend:** Next.js App Router, TS, Tailwind, shadcn/ui, Lucide, Recharts, RHF and Zod, TanStack Query, react-pdf.
- **No LangChain or LlamaIndex.** Own extractors (pdfplumber, pypdfium2, python-docx, markdown-it-py) and own structure-aware splitter.
- **No AGPL dependencies** (no PyMuPDF). Licenses recorded in `docs/THIRD_PARTY.md`.
- **Embeddings:** provider interface. Default local model `intfloat/multilingual-e5-small` (MIT, 384d, 512-token cap); bge-m3 optional on bigger servers. Profiles live in the `embedding_profiles` table; the workspace references one. Vectors live in `chunk_embeddings(chunk_id, profile_id)` with one partial HNSW index per profile. A model change means blue/green re-embed, never mixed vectors.
- **LLM:** one interface with Gemini, OpenAI, Anthropic and fake adapters. Model names in config only. Separate cheap model for rewriting and suggestions.
- **Jobs:** one generic `jobs` table (not under RLS; handlers set tenant context), claimed with `FOR UPDATE SKIP LOCKED`, 1 s polling, stale-lock recovery, exponential backoff. Emails go through it. Redis in V2.
- **Events:** transactional outbox `domain_events` (document.indexed, document.failed, question.unanswered, feedback.received). V3 webhooks consume it.
- **Storage:** interface; local disk now, S3/MinIO in V2. Random storage keys.

## How to work in this repo (learned in Phase 1)

- Run everything through Docker inside WSL. From PowerShell, multi-line `wsl bash -c` quoting breaks; put shell scripts in the scratchpad and run `wsl bash <script>`.
- Backend gate: `docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check . && mypy app && alembic check && pytest -q"`. The container user cannot write to the bind mount: run `ruff format` / `--fix` with `-u root`.
- Frontend: generate or modify `package-lock.json` only inside a Linux Node container (avoids npm's cross-platform optional-dependency bug). `npm_config_before=2026-10-31T00:00:00Z`.
- **Next.js 16 differs from training data:** read `frontend/node_modules/next/dist/docs/` before using an API. `middleware` is now `proxy.ts`; `cacheComponents` is on (wrap `useSearchParams` users in `<Suspense>`).
- Dependency cutoff 2026-10-31 (uv `exclude-newer`, npm `before`). Security fixes are allowed per package with a comment.
- Request-scoped DB sessions must be opened and closed in one generator (`api/deps.get_db`). A nested generator leaked an open transaction on errors (caught by tests).
- Hand-written migrations: keep naming identical to `models/base.NAMING_CONVENTION`; `alembic check` must report no drift.
- (Phase 2) SQLAlchemy 2.1: `Select[A, B]` (TypeVarTuple, not `tuple[...]`), iterate rows directly (`.tuples()` is deprecated). Base uses `eager_defaults=True`; never read DB-generated attributes after commit without it.
- (Phase 2) Next.js 16 with `cacheComponents`: dynamic params via `PageProps<"/route/[id]">` and `params.then(...)` inside `<Suspense>`; the signed-in shell sits in `<Suspense>`; signed-in pages set `export const instant = false`. **Always run `npm run build`**: dev mode hides prerender errors.
- (Phase 2) Dev web hot reload can miss changes (polling on a Windows mount): `docker compose restart web` before trusting a browser check.
- (Phase 2) Writing unicode escapes through the file tools turns them into literal characters; use `chr(0x...)` in Python source.
- Samples for manual testing: `samples/` (fictional), regenerated by `backend/scripts/make_samples.py`.
- (Phase 3) Tests always use `embedding_backend="fake"` and `llm_backend="fake"` (no network, no cost). Real providers only in evals and live checks.
- (Phase 3) Evals: `docker compose run --rm --no-deps -u root -v ./docs/evals:/out api python -m evals.run --config evals/configs/<name>.yaml --out /out`, then `python -m evals.compare /out`. About USD 0.03 and 4-5 minutes per run (free-tier 429s are retried). Only harness-produced numbers go in docs or the README.
- (Phase 3) Gate thresholds live in `app/rag/profiles.py` and must come from an eval report; never hand-tune on the holdout split.
- (Phase 3) Local embeddings: `docker compose --profile local-embeddings up -d embedder` (about 720 MB RAM; stop it when not needed).
- (Phase 3) Verify provider APIs with a small probe script before coding against them; model names and prices change (prices only from the official page, in `app/core/pricing.py`).
- (Phase 4) FastAPI and other libraries ship their own docs in the installed package (`fastapi/.agents/skills/fastapi/references/`, `next/dist/docs/`, `react-pdf/README.md`): read those, not memory. react-pdf 11 uses Suspense by default; we pass `suspense={false}`.
- (Phase 4) Chat SSE uses `app/api/sse.EventStreamResponse` (closes the generator on disconnect). Do every check in `ChatService.prepare_*` before streaming; never raise HTTP errors from inside the stream.
- (Phase 4) Tests swap AI providers through `app.state.engine_factory` and `app.state.cheap_llm_factory` (see `tests/integration/test_chat.py`); stop/cancel behaviour is tested at the service level.
- (Phase 4) `npm view` ignores `--before`: read `npm view <pkg> time --json` to pick versions published before the cutoff.
- (Phase 4) The dev web container sets `NODE_ENV=development`, which breaks `next build` (`/_global-error` useContext error). Verify the build with `docker compose -f compose.yaml build web`.
- (Phase 5) Production: `docker compose -f compose.yaml -f compose.prod.yaml ...` (or `COMPOSE_FILE=compose.yaml:compose.prod.yaml`); never plain `docker compose up` on a server. Test it locally with `SITE_ADDRESS=localhost` (Caddy's internal CA) and `E2E_IGNORE_HTTPS_ERRORS=1`.
- (Phase 5) Clean-machine checks use a separate project name (`-p citebase-clean`) so the dev volumes are untouched; `down -v` there also deletes that project's `web_node_modules`.
- (Phase 5) Demo data: `docker compose run --rm -v ./samples:/samples:ro api python -m app.cli seed [--password ...]`. Screenshots: `tests/e2e/screenshots.spec.ts` (README) and `tests/e2e/portfolio.spec.ts` (freelance portfolio, output in gitignored `portfolio/`); run them against a production build and look at every image.
- (Phase 4) E2E: build `frontend/e2e.Dockerfile` (Chromium only; mcr.microsoft.com pulls time out here) and run `npx playwright test` in it with `--network host`, mounting the `citebase_web_node_modules` volume (README). Set `E2E_SCREENSHOTS=<dir>` to save review screenshots and look at them.

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
