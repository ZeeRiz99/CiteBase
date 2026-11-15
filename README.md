# CiteBase

**Ask your documents. Get answers you can verify.**

CiteBase is a knowledge-base platform for businesses: upload documents, ask questions in plain
language, and get answers with citations to the exact page and passage. When the documents do not
contain the answer, it says so.

> Status: **Phase 2 (Documents)**: authentication, workspace isolation with row-level security, and a
> knowledge base that uploads, validates, extracts, chunks and keyword-indexes PDF, Word, Markdown and
> text files. The RAG engine (embeddings, retrieval, cited answers) comes next.
> See [docs/PROGRESS.md](docs/PROGRESS.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

Requirements: Docker Engine with Compose v2 (on Windows, Docker inside WSL2 works well).

```bash
cp .env.example .env          # development defaults; replace every secret before deploying
docker compose up -d --build  # first build takes a few minutes
```

On Windows, run the same commands from PowerShell in the repo folder by prefixing them with `wsl`
(for example `wsl docker compose up -d --build`).

| What | URL |
|---|---|
| App | http://localhost:8080 |
| API docs (development only) | http://localhost:8080/api/docs |
| Caught emails (Mailpit) | http://localhost:8025 |
| Postgres (owner role, for tools) | `localhost:5433` |

Stop the stack with `docker compose stop` (data is kept in Docker volumes). On Windows, `wsl --shutdown`
also stops WSL and returns its memory; the next `wsl docker compose up -d` brings everything back.

Try it: open the app, create an account, open Mailpit, click the confirmation link, then sign out,
use "Forgot password?" and follow the emailed link.

Then open **Knowledge base** and drag in the files from [`samples/`](samples/) (fictional demo
documents). Within seconds five show **Ready** and the scanned PDF shows **Needs OCR**; open a document
to see how it was split into passages.

## Development

The default `docker compose up` loads `compose.override.yaml`: source is bind-mounted, the API and
worker reload on change, and Next.js runs in dev mode. For a production-like run use
`docker compose -f compose.yaml up -d --build`.

```bash
# Backend: lint, types, schema drift, tests (real Postgres, fake email)
docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check . && mypy app && alembic check && pytest -q"

# Frontend: lint, types, unit tests
docker compose run --rm --no-deps web npm run check

# Logs
docker compose logs -f api worker
```

## Architecture at a glance

- **Caddy** serves one origin: `/` to Next.js, `/api` to FastAPI (cookies, CSRF and streaming stay simple).
- **FastAPI** (Python 3.12, SQLAlchemy 2, Alembic) with Argon2id, rotating refresh tokens in httpOnly cookies,
  signed double-submit CSRF and rate limiting.
- **Postgres 17 + pgvector**: app data, vectors, keyword search and the job queue, with
  **row-level security** isolating every workspace.
- **Worker**: database-backed job queue (`FOR UPDATE SKIP LOCKED`, retries with backoff).
- **Next.js 16** (App Router), Tailwind 4, shadcn/ui, TanStack Query, React Hook Form + Zod.

Product name, tagline and colors come from configuration (`PRODUCT_NAME`, `PRODUCT_TAGLINE` in `.env`;
design tokens in `frontend/app/globals.css`).
