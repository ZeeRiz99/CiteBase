# Third-party software

CiteBase is built on the open-source software below. Versions and licenses were read from the
installed packages (Python package metadata, each npm package's `package.json`) on 2026-11-17.
Transitive dependencies are not listed; run a license scanner (for example `pip-licenses` and
`license-checker`) when you need the full tree.

**Nothing here is copyleft for normal use.** One runtime library is LGPL-3.0 (`psycopg`); it is used
unmodified as a separately installed Python package, which the LGPL permits in proprietary
software. If you modify psycopg itself, you must publish those modifications.

## Backend (Python)

| Package | Version | License | Used for |
|---|---|---|---|
| fastapi | 0.162.0 | MIT | HTTP API |
| uvicorn | 0.54.0 | BSD-3-Clause | ASGI server |
| pydantic / pydantic-settings | 2.14.2 / 2.16.2 | MIT | Validation, configuration |
| sqlalchemy | 2.1.6 | MIT | Database access |
| alembic | 1.20.1 | MIT | Database migrations |
| psycopg | 3.3.6 | LGPL-3.0-only | PostgreSQL driver (see note above) |
| pgvector | 0.5.1 | MIT | Vector column type |
| pyjwt | 2.15.1 | MIT | Access tokens |
| argon2-cffi | 25.1.0 | MIT | Password hashing |
| email-validator | 2.3.0 | Unlicense | Email address validation |
| aiosmtplib | 5.1.3 | MIT | Sending email |
| structlog | 26.1.0 | MIT OR Apache-2.0 | Structured logging |
| python-multipart | 0.0.32 | Apache-2.0 | File uploads |
| pdfplumber | 0.11.10 | MIT | PDF text and table extraction |
| pypdfium2 | 5.14.0 | BSD-3-Clause, Apache-2.0 (bundles PDFium) | PDF rendering for extraction |
| python-docx | 1.2.0 | MIT | Word document extraction |
| tiktoken | 0.14.0 | MIT | Token counting for chunking |
| httpx | 0.28.1 | BSD-3-Clause | Calls to AI providers |

Local embedding service (optional `local-embeddings` profile):

| Package / model | Version | License |
|---|---|---|
| onnxruntime | 1.31.1 | MIT |
| tokenizers | 0.23.3 | Apache-2.0 |
| huggingface-hub | 2.4.0 | Apache-2.0 |
| numpy | 2.5.4 | BSD-3-Clause |
| intfloat/multilingual-e5-small (model weights, downloaded at first start) | - | MIT |

Development and test only (not shipped in the production image's runtime): pytest 9.2.0 (MIT),
pytest-asyncio 1.4.1 (Apache-2.0), pyyaml 6.0.3 (MIT), ruff 0.17.3 (MIT), mypy 2.4.1 (MIT),
pip-audit 2.10.1 (Apache-2.0), reportlab 5.1.0 (BSD; generates test fixtures and sample PDFs).

## Frontend (JavaScript)

| Package | Version | License | Used for |
|---|---|---|---|
| next | 16.4.6 | MIT | Web framework |
| react / react-dom | 19.3.0 | MIT | UI |
| @tanstack/react-query | 5.105.0 | MIT | Data fetching and caching |
| react-hook-form | 7.91.0 | MIT | Forms |
| @hookform/resolvers | 6.0.2 | MIT | Form validation bridge |
| zod | 4.6.7 | MIT | Validation schemas |
| radix-ui | 1.8.1 | MIT | Accessible UI primitives (via shadcn components) |
| class-variance-authority | 0.7.1 | Apache-2.0 | Component variants |
| cn | 0.5.1 | MIT | Class name merging |
| lucide-react | 1.65.0 | ISC | Icons |
| next-themes | 0.4.6 | MIT | Theme switching |
| sonner | 2.0.8 | MIT | Toast notifications |
| tw-animate-css | 1.4.0 | MIT | Animations |
| react-markdown | 10.1.0 | MIT | Rendering answers |
| remark-gfm | 4.0.1 | MIT | Tables and lists in answers |
| react-pdf | 11.0.0 | MIT | PDF source viewer |
| pdfjs-dist (via react-pdf) | 6.3.289 | Apache-2.0 | PDF rendering |

Development and test only: typescript 5.9.3 (Apache-2.0), eslint 9.39.5 (MIT), eslint-config-next
16.4.3 (MIT), tailwindcss and @tailwindcss/turbopack 4.3.3 (MIT), shadcn 4.23.0 (MIT, component
generator), vitest 5.0.5 (MIT), @vitejs/plugin-react 5.2.0 (MIT), jsdom 30.1.3 (MIT),
@testing-library/react 16.3.3, jest-dom 7.0.1 and user-event 14.6.8 (MIT), @playwright/test 1.64.1
(Apache-2.0), @types/* (MIT).

**Font:** Inter, loaded through `next/font/google` and served from your own domain (SIL Open Font
License 1.1).

## Container images

| Image | License of the main software |
|---|---|
| `python:3.12-slim-bookworm` | Python Software Foundation License; Debian packages under their own licenses |
| `node:24-bookworm-slim` | MIT (Node.js); Debian packages under their own licenses |
| `pgvector/pgvector:0.8.6-pg17-bookworm` | PostgreSQL License (PostgreSQL and pgvector) |
| `caddy:2.10-alpine` | Apache-2.0 |
| `axllent/mailpit:v1.27` (development only) | MIT |
