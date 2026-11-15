# CiteBase: progress log

## Current status

**Phase 2 (Documents): complete on branch `phase-2/documents`, awaiting approval.** Phase 1 was closed on 2026-11-14 (tag `phase-1`). Next: Phase 3 (RAG engine and evals).

## Completed

| Date | Phase | What |
|---|---|---|
| 2026-11-14 | 0 | Environment inspected; architecture proposal (`docs/ARCHITECTURE.md`); `CLAUDE.md`; git repo |
| 2026-11-14 | 1 | Docker Engine in WSL; Compose stack; config; structured logging; error envelope; migration 0001 with RLS; full auth; CSRF; rate limiting; audit log; outbox; DB job queue and worker; design tokens; landing skeleton; auth screens; app shell; dashboard; settings; CI |
| 2026-11-15 | 2 | Migration 0002 (documents, versions, pages, chunks + GIN keyword index, RLS); storage interface (local volume); upload validation (allow-list, magic bytes, size/page limits, encrypted PDF, DOCX macro and zip-bomb guards, encoding); per-workspace duplicate detection; extraction in a child process with timeout (PDF via pdfplumber with Markdown tables, header/footer removal, reflow, scanned detection; DOCX and MD by heading; TXT); structure-aware chunker with exact offsets, overlap, table headers and page/section soft boundaries; ingest job with stages, heartbeat, retry and resume from stored pages; versions that go live only once indexed; soft delete with scheduled purge and owner purge-now; download with sandbox CSP; domain events; dashboard counts; knowledge base and document detail screens with drag-and-drop upload and live status; sample documents |

## Phase 2 verification evidence

- Backend: ruff clean, mypy strict clean, `alembic check` no drift, **93 pytest tests pass** (52 new: validation, extractors per format, chunking invariants, ingestion end to end per format, scanned PDF, failure and retry, automatic retry, duplicates, limits, versions, download headers, delete and purge, roles, domain events, and workspace isolation on every document endpoint plus RLS on chunks). `pip-audit`: no known vulnerabilities.
- Frontend: ESLint 0 warnings, `tsc` clean, **26 Vitest tests pass**, production build passes, `npm audit --omit=dev`: 0 vulnerabilities.
- Live stack (through Caddy, real worker): **23/23** document checks (all four formats indexed in about 2 s, scanned PDF flagged, table as Markdown, header stripped, download, duplicate, delete, counts) and **19/19** Phase 1 auth regression checks.
- Browser (Playwright with installed Chrome): register, upload six files through the dropzone, statuses update live, detail page; no console errors; **0 px horizontal overflow at a 390 px mobile viewport**.

## Assumptions in force (Phase 0 questions not yet answered)

1. Repo lives at `D:\Projects\citebase`; dev containers poll for file changes.
2. English-first keyword search (configurable per workspace).
3. One deployment per client; branding through `.env` and web build arguments.
4. LLM keys not needed until Phase 3.

## Known issues and notes

- **CI has not run on GitHub yet** (no remote). The workflow runs the same commands that pass locally.
- **"Ready" means extracted, chunked and keyword-indexed.** Embeddings arrive in Phase 3 (the `embedding` status already exists).
- OCR is not performed: scanned PDFs are detected and reported as "Needs OCR", never indexed empty.
- CSV is deferred (not in the allow-list).
- PDF headings are not detected; PDF passages are cited by page, DOCX/MD by section.
- Chunks of superseded versions are kept until the document is purged (history); they are never served because retrieval joins on `current_version_id`.
- Collections: only the default collection is used in the UI; the API already lists collections and accepts `collection_id`.
- Uploading does not require a verified email yet (decide before public sign-up).
- The worker processes one job at a time; enough for V1, Redis workers in V2.
- Dev only: the in-memory rate limiter (5 registrations per hour per IP) trips during repeated manual testing; `wsl docker compose restart api` resets it.
- Next.js 16 dev "instant navigation" validation is opted out (`instant = false`) for the client-rendered signed-in pages.
- WSL idle shutdown is disabled (`.wslconfig`); `wsl --shutdown` frees memory.
- No Content-Security-Policy header on the app yet (planned for Phase 5); downloaded files are served with a sandbox CSP.

## Next step

**Phase 3, RAG engine and evals:** embedding providers (local multilingual-e5-small service plus API adapters) with the `chunk_embeddings` table, hybrid retrieval (pgvector + keyword, RRF), relevance gate calibrated on a golden set, generation with three LLM adapters plus a fake, server-side citation validation, a command-line `ask` tool, and the evaluation harness with a committed report. Needs at least one LLM API key for generation-quality metrics.
