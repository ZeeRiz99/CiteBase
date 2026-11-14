# CiteBase: progress log

## Current status

**Phase 1 (Foundation): approved and closed on 2026-11-14** (merged to `main`, tag `phase-1`). Phase 2 (Documents) has not started; it begins when the user says go.

## Completed

| Date | Phase | What |
|---|---|---|
| 2026-11-14 | 0 | Environment inspected; architecture proposal (`docs/ARCHITECTURE.md`); `CLAUDE.md`; git repo |
| 2026-11-14 | 1 | Docker Engine in WSL; Compose stack (Caddy, Postgres 17 + pgvector, Mailpit, migrate, api, worker, web); config; structured logging with redaction; error envelope; Alembic migration 0001 with RLS and grants; full auth (register, login, logout, refresh rotation with reuse detection, email verification, password reset, change password, profile); signed double-submit CSRF; rate limiting; audit log; outbox table; DB job queue and worker (email jobs with retry and payload scrubbing); design tokens; landing page skeleton; auth screens; app shell; dashboard; settings; CI workflow |

## Phase 1 verification evidence

- Backend: ruff and format clean, mypy strict clean, `alembic check` reports no drift, **41 pytest tests pass** against real Postgres (auth flows, CSRF, rate limits, refresh rotation and reuse, workspace isolation via RLS incl. pool-leak and forged-claim tests, worker retries).
- Frontend: ESLint (0 warnings), `tsc` clean, **14 Vitest tests pass** (API client CSRF/refresh/errors, safe redirects, login form).
- End-to-end smoke through Caddy at http://localhost:8080 (`register → email via worker → Mailpit → verify → refresh → logout → forgot → reset → login`): see the gate summary.

## Assumptions in force (Phase 0 questions not yet answered)

1. Repo stays on the Windows drive; dev containers poll for file changes.
2. English-first keyword search (configurable per workspace).
3. One deployment per client; branding through `.env` and web build arguments.
4. LLM keys not needed until Phase 3.

## Known issues and notes

- **CI has not run on GitHub yet**: there is no remote. The workflow runs the same commands that pass locally; confirm it is green after the first push.
- WSL idle shutdown is disabled in `%USERPROFILE%\.wslconfig` (`vmIdleTimeout=-1`, `instanceIdleTimeout=-1`) so the stack stays reachable; use `wsl --shutdown` to free memory.
- Dev and production images use separate names (`citebase-backend:dev`, `citebase-web:dev` vs the default names); a production build once overwrote the dev web tag (fixed in `61db251`).
- Dev hot reload runs through polling on a Windows bind mount; slower than native. Moving the repo into the WSL filesystem would fix it (Phase 0 question 1).
- A Content-Security-Policy header is not set yet (Next dev needs inline scripts and eval); add a production CSP in Phase 5.
- The login rate limiter is in-process (correct for a single API instance; Redis in V2).
- Email change, session list and account deletion are not built (settings shows the email as read-only).
- npm 11 now skips dependency install scripts unless approved (`unrs-resolver` postinstall skipped); lint, typecheck, tests and build all pass without it.

## Next step

**Phase 2, Documents:** upload with validation (extension, magic bytes, limits, duplicate hash), storage interface, PDF/DOCX/TXT/MD extraction with page and heading structure, `needs_ocr` detection, structure-aware chunking, ingest jobs with stages and retry, document versions and soft delete, knowledge-base screens.
