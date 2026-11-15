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
