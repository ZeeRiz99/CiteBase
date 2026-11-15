# End-of-build backlog

Known limits and follow-ups collected at each phase gate. **Agreed with the user (2026-11-15): these
are handled together after the last build phase, not during the phases.** Add new items at every gate;
tick them off in the final hardening pass.

## From Phase 1 (Foundation)

- [ ] Push to GitHub and confirm the CI workflow is green (no remote yet).
- [ ] Production Content-Security-Policy header for the app (downloads already use a sandbox CSP).
- [ ] Mobile check at a true phone viewport. *Done in Phase 2: 0 px overflow at 390 px; keep in the Playwright suite.*
- [ ] Faster dev hot reload: move the repo into the WSL filesystem, or accept polling on `D:\`.
- [ ] Rate limiter is in-process: fine for one API instance; Redis-backed limiter with V2 workers.
- [ ] Account features: change email, list and revoke active sessions, delete account.
- [ ] npm 11 skips dependency install scripts (`unrs-resolver`); decide whether to approve them.
- [ ] WSL idle shutdown is disabled on this laptop (`.wslconfig`); document for other machines.

## From Phase 2 (Documents)

- [ ] OCR for scanned PDFs (currently detected and flagged "Needs OCR", not converted).
- [ ] CSV support (extraction by row groups) once quality is verified.
- [ ] Heading detection in PDFs (font size/weight) so PDF passages also get section titles.
- [ ] Require a confirmed email before uploading (decide before public sign-up).
- [ ] Collections UI (API already supports `collection_id`); document-level permissions come with V2.
- [ ] Delete chunks of superseded versions after a grace period to save space (kept for history now).
- [ ] Parallel ingestion (worker runs one job at a time; Redis workers in V2).
- [ ] Dev-only: in-memory rate limit trips during repeated manual testing (`docker compose restart api` resets it).
- [ ] Revisit Next.js `instant = false` opt-out on signed-in pages if the shell becomes server-rendered.

## From Phase 3 (RAG engine and evals)

- [ ] Larger evaluation corpus (realistic size, hundreds of chunks): the 10-chunk demo corpus saturates retrieval metrics. Add per-client golden sets during onboarding.
- [ ] Live-verify the OpenAI and Anthropic adapters once keys exist (contract-tested only).
- [ ] Meter embedding tokens and cost (the Gemini embedding API returns no usage; currently excluded from cost reports).
- [ ] Recalibrate gate thresholds on each client's corpus; the demo corpus gap between off-topic and answerable similarity is narrow (about 0.07).
- [ ] Use a judge model from a different family than the answer model (self-preference bias); needs a second provider key.
- [ ] Production rate limits: free-tier Gemini returned HTTP 429 several times per eval run (absorbed by retries); move to a paid tier or add request pacing.
- [ ] Optional neighbor-chunk context expansion (in the design, not built); measure with the harness before adding.
- [ ] Calibrate gate thresholds for profile 3 (OpenAI embeddings) when a key is available.
- [ ] Ambiguous tables: asked for the *express* price, the model answered with a table's only (unlabelled) price column. Add a prompt rule ("if the source does not distinguish, say so") and a golden question for it, then re-run the evals.
- [ ] Local profile gate: one holdout question fell just under the calibrated 0.80 threshold (false refusal); recalibrate with more questions.
- [ ] Phase 2 fix applied early because it affected retrieval: PDF header/footer removal now works from two pages (was three).
