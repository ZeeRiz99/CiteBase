# Deploying CiteBase

This guide puts one CiteBase deployment on a Linux server with its own domain and HTTPS. Each
organization gets its own deployment (its own database, storage, branding and AI keys).

## 1. What you need

| Item | Notes |
|---|---|
| A Linux server | 2 vCPU and 4 GB RAM is enough for a team (the containers are capped at about 2.5 GB in total). Add 1 GB if you use local embeddings. Ubuntu 24.04 LTS or Debian 12 work. |
| Docker Engine and Compose | Compose **2.24 or newer** (the production file uses `!reset` and `!override`). Install from docs.docker.com/engine/install. |
| A domain name | An `A` (and optionally `AAAA`) record pointing at the server, for example `answers.example.com`. |
| Open ports | 80 and 443 (TCP), and 443 UDP for HTTP/3. Nothing else needs to be reachable. |
| An SMTP account | For sign-up confirmation and password-reset emails (any transactional email provider). |
| An AI provider key | Gemini by default; OpenAI or Anthropic also work (see "AI providers" below). |
| Disk | 10 GB plus about twice the size of the documents you will upload. |

## 2. Install

```bash
git clone <your-repository-url> citebase
cd citebase
cp .env.example .env
chmod 600 .env
```

Generate a separate random value for each secret (run it four times):

```bash
openssl rand -base64 36 | tr -d '/+=' | cut -c1-40
```

Edit `.env` and set **every** line below. The file is read only by Docker; never commit it.

```dotenv
ENVIRONMENT=production
APP_BASE_URL=https://answers.example.com
SITE_ADDRESS=answers.example.com
COOKIE_SECURE=true

PRODUCT_NAME=Acme Answers                  # your brand
PRODUCT_TAGLINE=Ask our documents. Get answers you can verify.

POSTGRES_PASSWORD=<random>
CITEBASE_OWNER_PASSWORD=<random>
CITEBASE_APP_PASSWORD=<random>
SECRET_KEY=<random, at least 32 characters>

SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USERNAME=<from your provider>
SMTP_PASSWORD=<from your provider>
EMAIL_FROM=Acme Answers <no-reply@example.com>

GEMINI_API_KEY=<your key>
MONTHLY_TOKEN_LIMIT=2000000                # AI tokens per workspace per month; 0 = unlimited
```

The database passwords are applied when the database is created (first start). Changing them
later requires changing them inside Postgres too, so pick them before the first start.

## 3. Start

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

The first build takes a few minutes. Then:

- `docker compose -f compose.yaml -f compose.prod.yaml ps` shows every service as running
  (`migrate` exits after applying the database schema; that is expected).
- `curl https://answers.example.com/api/v1/readyz` returns `{"status":"ok","database":"up"}`.
- Caddy obtains the HTTPS certificate on the first request; it renews automatically.

Open the site, create the first account (it becomes the owner of its workspace), confirm the email,
and upload documents under **Knowledge base**.

**Add your team** under **Settings → Team**: enter a colleague's email and a role. They get an email
with a link (valid 7 days) to choose a password and join. The link is also shown once for copying,
in case the email is slow. Roles:

| Role | Can do |
|---|---|
| Owner | Everything, including managing admins (one per workspace: whoever signed up) |
| Admin | Manage documents, the team (members and viewers), unanswered questions and answer traces |
| Member | Upload and update documents, ask questions, rate answers |
| Viewer | Ask questions and rate answers; cannot change documents |

An email address that already has an account cannot be invited yet (one workspace per account).

**Confirmed email first.** New accounts must open the confirmation link from their sign-up email
before they can upload documents or invite people (they can look around and ask questions before
that). Invited people are confirmed by their invitation link. Set `REQUIRE_VERIFIED_EMAIL=false`
only for internal installs without working email.

**Changing the sign-in email** is self-service under **Settings → Sign-in email**: CiteBase sends a
link to the new address, switches only when it is opened, emails a notice to the old address and
signs the account out everywhere.

To save typing, put the two file names in the environment once:

```bash
export COMPOSE_FILE=compose.yaml:compose.prod.yaml
docker compose ps
```

**Never run plain `docker compose up` on a server:** without `-f` (or `COMPOSE_FILE`) Compose also
loads `compose.override.yaml`, the development setup with source mounts and dev servers.

### Optional: a demo workspace

To show the product with fictional content, create the labeled demo account (DEMO DATA only):

```bash
docker compose run --rm -v ./samples:/samples:ro api python -m app.cli seed
```

It prints the demo login (`demo@example.com`) and a generated password once.

## 4. AI providers

| Setting | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini`, `openai` or `anthropic`; set the matching `*_API_KEY` |
| `LLM_MODEL` | `gemini-3.5-flash-lite` | The answering model |
| `LLM_CHEAP_MODEL` | `gemini-3.5-flash-lite` | Follow-up rewriting and suggested questions |
| `DEFAULT_EMBEDDING_PROFILE` | `2` (Gemini embeddings) | `1` uses the local model instead (below) |

Only Gemini has been verified against the live API so far; the OpenAI and Anthropic adapters are
covered by contract tests. Cost estimates in the admin trace use the prices in
`backend/app/core/pricing.py`; models without an entry show "price not configured".

**Local embeddings** (documents are embedded on your server; answers still use the AI provider):

```bash
docker compose -f compose.yaml -f compose.prod.yaml --profile local-embeddings up -d embedder
```

Set `DEFAULT_EMBEDDING_PROFILE=1` before creating workspaces. The model (about 120 MB) downloads on
first start; the service needs about 1 GB of RAM.

**Text recognition (OCR).** Scanned PDFs, scanned pages inside normal PDFs, and PNG/JPEG photos are
read with Tesseract inside the worker: on your server, at no AI cost, a few seconds per page.

| Setting | Default | Notes |
|---|---|---|
| `OCR_ENABLED` | `true` | `false` flags scans as "Needs OCR" instead of reading them |
| `TESSERACT_LANGS` | `eng` | Languages installed when the image is built, space-separated Tesseract codes (`eng deu fra ara urd`) |
| `OCR_LANGUAGES` | `eng` | Languages used for recognition, the same codes joined with `+` (`eng+deu`) |
| `OCR_MAX_PAGES` | `100` | Longer scans are flagged "Scan too long"; split them into smaller files |

After changing `TESSERACT_LANGS`, rebuild: `docker compose up -d --build api worker`. Recognition
quality depends on the scan: 300 DPI, straight pages and good contrast work best. The document page
shows the average recognition confidence and warns below 70%.

**Provider rate limits.** Free AI tiers allow only a few requests per minute. CiteBase retries
briefly when the provider says "too many requests", but answers slow down and indexing large
document sets takes longer. Use a paid tier for client deployments and set a spending limit in the
provider's console.

## 5. Email delivery

Invitations, email confirmation and password resets are sent through your SMTP provider. So that
they land in the inbox and not in spam, set these DNS records for the domain in `EMAIL_FROM`
(your provider shows the exact values):

| Record | What it does |
|---|---|
| **SPF** (TXT on the domain, e.g. `v=spf1 include:<provider> ~all`) | Lists the servers allowed to send for the domain |
| **DKIM** (TXT or CNAME the provider gives you) | Signs each email so receivers can verify it |
| **DMARC** (TXT on `_dmarc.<domain>`, e.g. `v=DMARC1; p=none; rua=mailto:you@<domain>`) | Tells receivers what to do with mail that fails the checks; start with `p=none`, move to `quarantine` once reports look clean |

Send a test by inviting yourself to a second address and check the message headers show
`spf=pass`, `dkim=pass` and `dmarc=pass`.

## 6. Backups

Everything worth keeping lives in two Docker volumes: the database (`pgdata`) and the uploaded
files (`storage`). `infra/backup.sh` writes both at the same time and removes copies older than
14 days:

```bash
infra/backup.sh                    # -> backups/db-<date>.dump and backups/storage-<date>.tgz
infra/backup.sh /srv/backups 30    # another folder, keep 30 days
```

Run it daily with cron (`crontab -e` as the user that runs Docker; adjust the path):

```cron
15 3 * * * cd /srv/citebase && infra/backup.sh >> backups/backup.log 2>&1
```

**Copy the backups off the server.** A backup on the same disk does not survive the disk. Use your
host's object storage or a tool such as `rclone` or `restic` after the backup line, for example
`rclone copy /srv/citebase/backups remote:citebase-backups`.

Keep `.env` in your password manager: without `SECRET_KEY` and the database passwords a restore
still works, but everyone must sign in again.

**Restore** onto a fresh install (same `.env`):

```bash
docker compose up -d --wait postgres     # --wait: until first-start setup has finished
docker compose exec -T postgres pg_restore -U postgres -d citebase --clean --if-exists < backups/db-<stamp>.dump
docker compose run --rm --no-deps -u root -v "$PWD/backups":/backup --entrypoint sh api \
  -c "tar -xzf /backup/storage-<stamp>.tgz -C /data/storage"
docker compose up -d
```

## 7. Upgrades

```bash
git pull
docker compose up -d --build
```

The `migrate` service applies database changes before the API starts. Take a backup first.

## 8. Operations

| Task | Command |
|---|---|
| Logs (JSON lines) | `docker compose logs -f api worker` |
| Health (process up) | `GET /api/v1/healthz` |
| Readiness (database reachable) | `GET /api/v1/readyz` |
| Stop everything | `docker compose down` (data is kept in volumes) |
| Ask from the command line | `docker compose exec api python -m app.cli ask "..." --email you@example.com --trace` |
| Re-index after a model change | `docker compose exec api python -m app.cli reindex --email you@example.com` |
| Change one workspace's monthly AI allowance | `docker compose exec api python -m app.cli token-limit 5000000 --email admin@client.com` (`0` = unlimited, `default` = back to `MONTHLY_TOKEN_LIMIT`) |
| Back up now | `infra/backup.sh` |

The AI allowance is an operator setting on purpose: workspace admins see it under **Settings** but
cannot raise it themselves.

## 9. Security checklist

- [ ] Every secret in `.env` is a fresh random value; `.env` is `chmod 600` and not in git.
- [ ] `ENVIRONMENT=production` (API docs are off; logs are JSON) and `COOKIE_SECURE=true`.
- [ ] Only ports 80 and 443 are open in the firewall (Postgres is not published in production).
- [ ] Real SMTP is configured with SPF, DKIM and DMARC; Mailpit is not running (`docker compose ps`).
- [ ] `infra/backup.sh` runs daily from cron, copies go off the server, and a restore has been tested once.
- [ ] The AI provider account has a spending limit; `MONTHLY_TOKEN_LIMIT` matches your budget.
- [ ] The server gets operating-system security updates (for example `unattended-upgrades`).

## 10. Known limits of this version

- One API instance per deployment: the request rate limiter lives in memory. Do not scale the
  `api` service to several replicas yet. Restarting the API also resets the limits.
- Text recognition (OCR) is English by default, limited to 100 pages per scanned file, and takes a
  few seconds per page. Passages read from a scan are shown as text next to the page image; they are
  not marked on the image itself.
- One workspace per account: people who already have an account cannot be invited to another
  workspace. Document-level permissions are not available; every member sees every document.
- Plan limits shown on the pricing page (pages, questions, seats) are not enforced; only the monthly
  AI allowance is.
- See `docs/BACKLOG.md` for the full list.
