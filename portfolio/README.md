# CiteBase portfolio images

Screenshots of CiteBase `v1.3.0` for freelance profiles and client presentations. Everything shown is
the labeled demo workspace (**fictional DEMO DATA**: Northwind Outfitters and its people do not exist).

| Folder | What | Use it for |
|---|---|---|
| `upwork/` | 9 framed showcase images, 2000 x 1500 (4:3) | Upwork portfolio; `00-cover.png` as the cover |
| `fiverr/` | The same 9, 2560 x 1538 (Fiverr's recommended shape at 2x) | Fiverr gig gallery |
| `raw/` | 17 retina screenshots (desktop 2880 x 1800, phone 1170 x 2532, one full landing page) | LinkedIn, Behance, your own site, case studies |

Showcase set:

| # | Image | Shows |
|---|---|---|
| 00 | cover | Landing page: AI knowledge base with verifiable citations |
| 01 | cited-answers | Streaming answer with citation chips and sources panel |
| 02 | source-viewer | A citation opening the PDF with the passage highlighted |
| 03 | honest-refusal | "Couldn't find it" instead of guessing; honest table answer above it |
| 04 | answer-trace | Admin "Why this answer?": retrieval scores and thresholds |
| 05 | knowledge-base | Documents, scans and photos indexed, with OCR tags |
| 06 | dashboard | Usage and quality at a glance |
| 07 | scans-and-photos | A scanned notice answered and cited (OCR) |
| 08 | team | Team invitations with admin, member and viewer roles |

## Regenerate after visual changes

1. Create a demo workspace with the fictional samples:
   `docker compose run --rm -v ./samples:/samples:ro api python -m app.cli seed --email <demo-email> --password <password>`
2. Serve the production web build: `docker compose -f compose.yaml build web && docker compose -f compose.yaml up -d --no-deps web`
3. Capture (from the repo root, with the e2e image from the README):
   `docker run --rm --network host --ipc=host -v "$PWD":/repo -v "$PWD/portfolio":/portfolio -v citebase_web_node_modules:/repo/frontend/node_modules -e DEMO_EMAIL=<demo-email> -e DEMO_PASSWORD=<password> -e PORTFOLIO_OUT=/portfolio -w /repo/frontend citebase-e2e:1.64.1 npx playwright test portfolio`
4. Go back to the dev server: `docker compose up -d --no-deps web`, and look at every image.
