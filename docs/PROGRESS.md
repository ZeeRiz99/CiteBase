# CiteBase: progress log

## Current status

**Phase 5 (polish and release): complete on branch `phase-5/release`, awaiting approval.** Phases 1-4 are closed (tags `phase-1` to `phase-4`). On approval: merge, tag `v1.0.0`, then the end-of-build backlog pass (`docs/BACKLOG.md`).

## Completed

| Date | Phase | What |
|---|---|---|
| 2026-11-14 | 0 | Environment inspected; architecture proposal (`docs/ARCHITECTURE.md`); `CLAUDE.md`; git repo |
| 2026-11-14 | 1 | Docker Engine in WSL; Compose stack; config; structured logging; error envelope; migration 0001 with RLS; full auth; CSRF; rate limiting; audit log; outbox; DB job queue and worker; design tokens; landing skeleton; auth screens; app shell; dashboard; settings; CI |
| 2026-11-15 | 2 | Documents: upload validation, isolated extraction, structure-aware chunking, keyword index, versions, delete and purge, knowledge base UI, sample documents |
| 2026-11-15 | 3 | Embedding profiles and per-profile vectors; provider layer (Gemini live, OpenAI/Anthropic contract-tested); local embedder; hybrid retrieval; calibrated relevance gate; versioned prompts; citation validation and regenerate-once; follow-up rewriting; CLI; evaluation harness with reports |
| 2026-11-16 | 4 | Migration 0004 (conversations, messages, message_sources, feedback, unanswered_questions, usage_events; RLS); SSE chat endpoint on the RAG engine with stop/cancel handling; regenerate; feedback; admin trace; unanswered queue; usage events and monthly token limit; per-user chat rate limit; suggested questions from real passages; passage context endpoint; purge blanks stored snippets; three-pane chat UI (conversation list, streaming answers with citation chips and hover previews, evidence badge, stop, regenerate, copy, rating with comment, sources panel, mobile tabs); source viewer (PDF page with text-layer highlight, text formats highlighted by stored offsets, version notice); admin "why this answer?" sheet; unanswered page; dashboard question stats and usage meter; Playwright golden-path test |
| 2026-11-17 | 5 | Landing page (measured quality with caveat, integrations with planned items labeled, illustrative pricing, FAQ, footer); icons and share image generated from branding; labeled demo seed (`app.cli seed`); production overlay with automatic HTTPS (`compose.prod.yaml`); configuration passthrough for SMTP/models/limits; deployment guide with backup and restore; asset brief; README rewrite with screenshots and diagrams; reproducible README screenshots and freelance portfolio images; clean-machine run; fixes found on the way (Postgres first-start readiness race, citation preview covering the passage, evidence badge on refusals) |

## Phase 5 verification evidence

- **Clean-machine run** (fresh `git clone` in the WSL home, `.env.example` plus one provider key):
  - README quick start: build, all services healthy, `readyz` ok; `app.cli seed` created the demo workspace (5 indexed, 1 needs OCR); golden path passed.
  - Production overlay (`SITE_ADDRESS=localhost`, `ENVIRONMENT=production`): HTTP 308 to HTTPS, HSTS header, Secure cookies, API docs 404, Postgres not published, Mailpit not running, share image served with an absolute `og:image` URL; golden path passed over HTTPS on the production images.
  - Backup and restore drill from `docs/DEPLOYMENT.md`: after `down -v` and restore, the same counts (users, documents, vectors), the demo account signs in (200) and an original file downloads (200). The first attempt failed and exposed the Postgres readiness race, fixed in `compose.yaml` and the guide.
- **Images:** 8 README screenshots (`docs/screenshots/`) and 26 portfolio images (`portfolio/`, gitignored: 12 retina screenshots, 7 framed at 2000x1500 for Upwork, 7 at 2560x1538 for Fiverr), all from the production build and the labeled demo workspace; reviewed by eye.
- Final test results are in the Phase 5 report (backend, frontend, audits).

## Phase 4 verification evidence

- Backend: ruff and mypy strict clean, `alembic check` no drift, **158 pytest tests pass** (16 new in `tests/integration/test_chat.py`: streamed answer saved with sources; refusal logged, counted and resolvable; follow-up rewritten with history; regenerate latest only; feedback and helpful rate; trace with signals/thresholds/usage; monthly token limit; chat rate limit; errors before streaming (too long, blank, AI not configured, turn in progress); provider error mid-answer; Stop via close and via cancel saves the partial answer and closes the provider stream; passage context and purge; suggested questions cached per document set; list/search/rename/delete; workspace isolation on every chat endpoint). `pip-audit`: no known vulnerabilities.
- Frontend: eslint and tsc clean, **39 Vitest tests pass** (13 new: SSE parser, citation linking, location labels, PDF passage matching incl. hyphenation, ligatures and passages continuing on the next page, HTML escaping); production image builds; `npm audit --omit=dev`: 0 vulnerabilities.
- **End to end** (Playwright 1.64.1, Chromium, real Gemini through Caddy, 38-52 s): register, upload two samples, ask, citation chip, Markdown passage highlighted, PDF page rendered with the passage highlighted, rating persists, off-topic refusal, history after reload, refusal listed under Unanswered. Screenshots were reviewed.
- Live API check (curl through Caddy, real Gemini): `meta` at 0.7 s, first token at 1.9 s, cited answer at 2.0 s; follow-up rewritten; off-topic refused at the gate; Stop recorded as `stopped`; trace shows real tokens and cost (USD 0.000173 for one answer).

## Assumptions in force

1. Repo lives at `D:\Projects\citebase`; dev containers poll for file changes.
2. English-first keyword search (configurable per workspace).
3. One deployment per client; branding through `.env` and web build arguments.
4. Gemini is the default provider (key in the gitignored root `.env`); OpenAI/Anthropic adapters are ready but unverified live.
5. Monthly AI allowance defaults to 2,000,000 tokens per workspace (`MONTHLY_TOKEN_LIMIT`; 0 = unlimited).

## Known issues

All known limits are collected per phase in [`docs/BACKLOG.md`](BACKLOG.md) and are handled after the last build phase, as agreed.

## Next step

**On approval:** merge `phase-5/release`, tag `v1.0.0`. Then the end-of-build backlog pass: work through `docs/BACKLOG.md` (Phases 1-5), as agreed.
