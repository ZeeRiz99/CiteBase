# CiteBase: progress log

## Current status

**Phase 0 (Discovery): complete, awaiting approval.** No application code written.

## Completed

| Date | Phase | What |
|---|---|---|
| 2026-11-14 | 0 | Environment inspected; architecture proposal in `docs/ARCHITECTURE.md`; `CLAUDE.md` created; git repo initialized |

## Open questions for the user (from ARCHITECTURE.md §12)

1. Move the repo into the WSL filesystem (`/home/dell/projects/citebase`)? Recommended.
2. English-first or multilingual clients (FTS config, eval set)?
3. One deployment per client or a shared multi-tenant SaaS (where branding lives)?
4. Which LLM API keys are available for development and evals?

## Known issues and environment notes

- Docker is not installed. The user must run the prerequisite commands in ARCHITECTURE.md §10 (needs `sudo`).
- WSL has 3.7 GiB RAM by default; raise it to 5 GB through `.wslconfig`.
- Native Postgres 18 runs in WSL on :5432; the Compose Postgres will use :5433.
- The machine has 7.8 GB RAM. On 2026-11-14, closing Chrome, Edge, WhatsApp, Phone Link and OneDrive raised free RAM from 1.8 to 3.4 GB. Keep browsers light while running the stack.

## Next step

After approval and the prerequisites: **Phase 1, Foundation.** Compose stack, config, Alembic base with RLS roles, authentication with email flows, design tokens and app shell, and CI.
