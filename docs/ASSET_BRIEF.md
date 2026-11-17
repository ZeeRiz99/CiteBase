# Asset brief

For a designer producing final brand assets for CiteBase (or a client's white-label deployment).
Everything below already exists in a working first version; this brief says what to replace,
in which format, and which rules every asset must keep.

## The product in one line

Upload business documents, ask questions in plain language, get answers with clickable citations
to the exact page, and an honest "not in your documents" when the answer is not there.
Tone: calm, precise, trustworthy. Not playful, not "AI magic".

## Rules every asset must follow

1. **No invented proof.** No fake customer logos, testimonials, ratings or usage numbers. Quality
   numbers come only from `docs/evals/` and always carry their caveat (small demo corpus).
2. **Fictional content is labeled.** Screens and illustrations use the fictional companies
   *Northwind Outfitters* (samples) or *Larkspur Outfitters* (evaluation corpus), never a real company.
3. **White-label safe.** The product name, tagline and colors come from configuration
   (`PRODUCT_NAME`, `PRODUCT_TAGLINE`, `frontend/app/globals.css`). Assets that appear inside the
   app must not hard-code "CiteBase" in a raster image; use SVG/text so a client's name can replace it.
4. **Accessible.** Text pairs meet WCAG AA (4.5:1). Icons have text labels in the UI.

## Design tokens (source of truth: `frontend/app/globals.css`)

| Role | Value |
|---|---|
| Navy (base, sidebar, hero) | 950 `#061128`, 900 `#0b1b33`, 800 `#12284a`, 700 `#1b3a66`, 600 `#2a5288` |
| Navy tints (surfaces) | 100 `#e4ebf5`, 50 `#f3f6fb` |
| Teal (primary action, citations) | 700 `#0f766e` (5.5:1 on white), 600 `#0d9488`, 500 `#14b8a6`, 100 `#ccfbf1`, 50 `#effdfa` |
| Cyan accent | 400 `#22d3ee`, 300 `#67e8f9` |
| Text | ink `#0b1b33`, body `#334155`, subtle `#526178` |
| Status | success `#15803d`, warning `#b45309`, destructive `#b42318` |
| Type | Inter (Google Fonts), scale 12/14/16/18/20/24/30/36/48 |
| Radius | 6 / 10 / 14 px |
| Icons | Lucide only (stroke icons, 1.5-2 px) |

## Assets

| Asset | Current state | Where | Needed |
|---|---|---|---|
| Logo mark | SVG: a document with a teal verified badge | `frontend/components/brand/logo.tsx`, `app/icon.svg`, `components/brand/mark-svg.ts` | Refined mark; keep it legible at 16 px and as a single-color version |
| Wordmark | Product name set in Inter Semibold next to the mark | `logo.tsx` | Keep as live text (white-label); optional custom lockup for CiteBase itself |
| Favicon | `app/icon.svg` (SVG) | `frontend/app/` | Same mark; an `.ico` fallback is optional |
| Apple touch icon | Generated at build, 180 px | `app/apple-icon.tsx` | Fine as generated unless the mark changes |
| Share preview (Open Graph) | Generated at build from product name and tagline, 1200x630 | `app/opengraph-image.tsx` | Optional richer layout; must stay generated (per-deployment branding) |
| Hero illustration | HTML/CSS mock of a cited answer with fictional content | `app/(marketing)/page.tsx` (`HeroIllustration`) | Optional animated version showing a citation being clicked; keep it code-drawn, not a screenshot |
| Empty-state illustrations | One SVG (empty knowledge base) | `components/brand/empty-documents.tsx` | A small set in the same flat navy/teal style: empty chat, nothing unanswered, document removed |
| Product screenshots | Captured by Playwright from the labeled demo workspace | `docs/screenshots/*.png` | Recapture after visual changes (below) |

## Recapturing screenshots

Screenshots are reproducible, never hand-edited:

1. Start the stack and create the demo workspace:
   `docker compose run --rm -v ./samples:/samples:ro api python -m app.cli seed --password <choose one>`
2. Run the capture spec (Chromium image from `frontend/e2e.Dockerfile`):

```bash
docker run --rm --network host --ipc=host -v "$PWD":/repo -v citebase_web_node_modules:/repo/frontend/node_modules \
  -w /repo/frontend -e DEMO_PASSWORD=<the password> -e E2E_SCREENSHOTS=/repo/docs/screenshots \
  citebase-e2e:1.64.1 npx playwright test screenshots
```

Use a production build (no development badge) and a 1440x900 viewport, as the spec does.
