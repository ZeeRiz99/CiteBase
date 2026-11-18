# End-of-build backlog

Known limits and follow-ups collected at each phase gate. **Agreed with the user (2026-11-15): these
are handled together after the last build phase, not during the phases.**

The pass started after `v1.0.0` (2026-11-17). Every item from the phase lists is sorted into one of
the groups below; the original phase lists follow with each item's outcome.

**Project closed at `v1.3.0` (2026-11-18).** Passes 1 and 2 and OCR are released. Everything still open
below is optional and waits for a client need or the owner's decision:
- Done: pushed to GitHub (CI green).
- Decided: no license for now; free Gemini tier until a real client (then billing or the client's own key).
- Still open: confirm pricing before selling; real client documents for quality checks.

## Status of the backlog pass

### Pass 1: hardening (done, branch `hardening/pass-1`)

- [x] **Team invitations and roles** (found during the pass: the pricing cards promised team seats
      but there was no way to add a teammate). Invite by email, accept page, member list, role
      changes, removal, workspace rename. See ARCHITECTURE "Decisions made during the backlog pass".
- [x] Viewer role made useful: viewers ask and rate; document controls hidden for roles that cannot
      use them.
- [x] Content-Security-Policy in production builds; the golden-path test fails on any violation.
- [x] Ambiguous tables: prompt `answer-v2`, golden question t07, evaluation re-run.
- [x] Phone-width chat checked in a Playwright test (tabs, answer, sources, passage, no sideways
      scroll); fixed long conversation titles and the hover-only actions menu on touch screens.
- [x] Chat no longer says "no documents" when the summary request fails.
- [x] Source labels no longer repeat the document title.
- [x] Trigram index for conversation search.
- [x] Operator command for a workspace's AI allowance (`app.cli token-limit`), shown read-only in
      Settings.
- [x] `infra/backup.sh` with pruning, cron example, off-site copy, SPF/DKIM/DMARC guidance,
      provider rate-limit note (DEPLOYMENT.md).
- [x] `docs/THIRD_PARTY.md` from installed package metadata.
- [x] README: Windows/WSL development notes (polling, idle shutdown, disk compaction), three e2e
      tests.

### Pass 2: product gaps (proposed next, needs your go-ahead)

- [x] Change email with confirmation (branch `pass-2/accounts`).
- [ ] List and revoke active sessions; delete account (GDPR-style request).
- [x] Require a confirmed email before uploading or inviting: on by default (`REQUIRE_VERIFIED_EMAIL`).
- [ ] Meter embedding tokens and cost (estimated with the tokenizer, labeled "estimated"); decide
      whether they count against the monthly AI allowance.
- [ ] Generation timeout with a fallback model, after measuring latency percentiles.
- [x] Occasional false refusal by the answer model (retry once when the gate is strong, done): once in 21 tries (2026-11-17), Flash-Lite refused "How many days do I have to return a regular item?" although the relevance gate passed with strong evidence (the same workspace then answered 10 of 10). Retry once when the gate is strong but the model refuses, and count these in the trace.
- [ ] Heading detection in PDFs (font size and weight) so PDF passages get section titles.
- [ ] Deterministic CI stack for the e2e tests (fake providers), so they run on every push.
- [ ] Settings: show this month's AI usage next to the allowance for admins.

### OCR follow-ups

- [ ] Highlight recognized passages on the scan image itself (store Tesseract word boxes per page).
- [ ] Automatic page rotation for upside-down or sideways scans (Tesseract orientation detection).
- [ ] Languages beyond English: documented (`TESSERACT_LANGS`, `OCR_LANGUAGES`); add per-workspace choice if clients need mixed languages.
- [ ] Image formats beyond PNG/JPEG (TIFF, HEIC from iPhones).
- [ ] A scanned document and golden questions in the evaluation corpus.

### V2 features (larger; need your priority)

- [ ] **Plan limits and billing**: pages, questions and seats per plan, enforced; payment provider.
      The pricing cards are display only until then.
- [ ] **Website chat widget** (planned on the pricing cards).
- [x] **OCR for scanned PDFs and images**: done on branch `feature/ocr` (Tesseract; scanned PDFs, scanned pages, PNG/JPEG).
- [ ] **Q&A export** (planned on the pricing cards).
- [ ] **Public API and webhooks** (planned on the pricing cards).
- [ ] Multi-workspace accounts (invite people who already have an account; workspace switcher).
- [ ] Collections UI and document-level permissions.
- [ ] "Ask about this document" from the document page.
- [ ] Activity feed on the dashboard.
- [ ] Streaming resume after a network drop.
- [ ] Localized refusal sentence per workspace.
- [ ] CSV support.
- [ ] Neighbor-chunk context expansion (measure with the harness first).
- [ ] Parallel ingestion and a Redis-backed rate limiter (needed to run several API instances).

### Needs you (decisions or accounts only you can provide)

- [ ] **Push to GitHub** (no remote yet) so the CI workflow runs.
- [ ] **License**: proprietary or open source, before publishing the repository.
- [ ] **Confirm the pricing** (Free $0, Starter $29, Growth $79, Business $199) before selling.
- [ ] **OpenAI / Anthropic keys** to verify those adapters live and calibrate their gate thresholds
      (also enables a judge model from a different family than the answer model).
- [ ] **A paid Gemini tier** for client deployments (free tier returns HTTP 429 under load).
- [ ] **Real client documents** (with permission) to measure PDF highlight precision and recalibrate
      the relevance gate on a realistic corpus.

### Decided: not doing, or done differently

- Prune chunks of superseded versions: **kept** on purpose (old citations need them; see
  ARCHITECTURE).
- Move the repo into the WSL filesystem for faster reload: **not doing**; polling on `D:` works, the
  README explains the occasional restart.
- npm 11 skipped install scripts for `unrs-resolver`: **not needed**; it ships prebuilt binaries
  and lint runs cleanly without the script.
- Settings UI for admins to change the AI allowance: **replaced** by the operator command (customers
  must not raise their own AI spend once plans are billed).

## Original lists by phase (with outcome)

### From Phase 1 (Foundation)

- [ ] Push to GitHub and confirm the CI workflow is green. → *Needs you.*
- [x] Production Content-Security-Policy header. → *Pass 1.*
- [x] Mobile check at a true phone viewport. → *Phase 2 (pages) and pass 1 (chat), in Playwright.*
- [x] Faster dev hot reload. → *Decided: keep polling; documented.*
- [ ] Redis-backed rate limiter with several API instances. → *V2.*
- [ ] Account features: change email, sessions, delete account. → *Pass 2.*
- [x] npm 11 skips `unrs-resolver` install scripts. → *Decided: not needed.*
- [x] WSL idle shutdown note for other machines. → *README.*

### From Phase 2 (Documents)

- [x] OCR for scanned PDFs. → *Done (`feature/ocr`).*
- [ ] CSV support. → *V2.*
- [ ] Heading detection in PDFs. → *Pass 2.*
- [ ] Require a confirmed email before uploading. → *Pass 2.*
- [ ] Collections UI and document-level permissions. → *V2.*
- [x] Delete chunks of superseded versions. → *Decided: keep.*
- [ ] Parallel ingestion. → *V2.*
- [x] Dev-only in-memory rate limit during repeated testing. → *Documented (`docker compose restart api`).*
- [ ] Revisit Next.js `instant = false` if the shell becomes server-rendered. → *Only if that happens.*

### From Phase 3 (RAG engine and evals)

- [ ] Larger evaluation corpus and per-client golden sets. → *Needs you (client documents).*
- [ ] Live-verify the OpenAI and Anthropic adapters. → *Needs you (keys).*
- [ ] Meter embedding tokens and cost. → *Pass 2.*
- [ ] Recalibrate gate thresholds per client corpus. → *Needs you (client documents); the harness does it.*
- [ ] Judge model from a different family. → *Needs you (second provider key).*
- [ ] Production rate limits (free-tier 429). → *Needs you (paid tier); documented.*
- [ ] Neighbor-chunk context expansion. → *V2.*
- [ ] Calibrate gate thresholds for profile 3 (OpenAI embeddings). → *Needs you (key).*
- [x] Ambiguous tables (express price from an unlabelled column). → *Pass 1: prompt `answer-v2`, t07.*
- [ ] Local profile gate: one holdout false refusal at 0.80. → *Needs a larger question set.*
- [ ] Generation latency outliers; timeout with fallback model. → *Pass 2.*
- [x] PDF header/footer removal from two pages. → *Done in Phase 3.*

### From Phase 4 (Chat and source viewer)

- [ ] Playwright in CI with a deterministic stack. → *Pass 2.*
- [x] Settings UI for the monthly token limit. → *Replaced by the operator command; shown in Settings.*
- [ ] Meter query-embedding tokens. → *Pass 2.*
- [ ] PDF highlight precision on real client PDFs. → *Needs you (client documents).*
- [ ] "Ask about this document". → *V2.*
- [ ] `/dashboard/activity` feed. → *V2.*
- [ ] Streaming resume. → *V2.*
- [x] Conversation title search index. → *Pass 1 (trigram index).*
- [ ] Localized refusal sentence. → *V2.*
- [x] Mobile check of the three-pane chat at 390 px. → *Pass 1 (`mobile-chat` test).*
- [ ] Dev-only npm advisories: now 10 moderate (was 12) in the shadcn CLI and typescript-eslint's
      transitive dependencies; the only fix is a forced major upgrade; runtime dependencies: 0.
      → *Recheck at each upgrade.*
- [x] `mcr.microsoft.com` pulls time out; slim e2e image. → *Environment note; workaround in place.*
- [x] Create `docs/THIRD_PARTY.md`. → *Pass 1.*

### From Phase 5 (Polish and release)

- [ ] License file. → *Needs you.*
- [ ] Confirm final pricing. → *Needs you.*
- [ ] Plan limits and billing. → *V2.*
- [ ] Features shown as "planned" on the pricing cards (widget, Q&A export, API and webhooks; OCR is done). → *V2.*
- [x] Source location repeats the document title. → *Pass 1.*
- [x] SPF/DKIM/DMARC and a backup cron example. → *Pass 1.*
- [x] Automated backups. → *Pass 1 (`infra/backup.sh` with pruning; off-site copy documented).*
- [x] WSL virtual disk does not shrink. → *README.*
