import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * Portfolio images for freelance platforms, from the labeled demo workspace (fictional DEMO DATA).
 * Runs only when PORTFOLIO_OUT and DEMO_PASSWORD are set. Use a production build (no dev badge).
 *
 *   raw/       retina screenshots (desktop 2880x1800, phone 1170x2532)
 *   upwork/    framed showcase images, 2000x1500 (4:3; Upwork: 1000-4000 px wide, horizontal frame)
 *   fiverr/    framed showcase images, 2560x1538 (Fiverr recommends 1280x769, max 4000x2416)
 */
const OUT = process.env.PORTFOLIO_OUT;
const PASSWORD = process.env.DEMO_PASSWORD;
test.skip(!OUT || !PASSWORD, "set PORTFOLIO_OUT and DEMO_PASSWORD to capture portfolio images");
test.describe.configure({ mode: "serial" });

const raw = (name: string) => path.join(OUT!, "raw", `${name}.png`);

async function snap(page: Page, name: string, fullPage = false) {
  await page.waitForTimeout(500); // transitions and fonts
  await page.screenshot({ path: raw(name), fullPage });
}

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.DEMO_EMAIL ?? "demo@example.com");
  await page.getByLabel("Password").fill(PASSWORD!);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

// Remove the demo account's earlier conversations so screens look like first use.
async function clearConversations(page: Page) {
  const csrf = (await (await page.request.get("/api/v1/auth/csrf")).json()) as { csrf_token: string };
  const conversations = (await (await page.request.get("/api/v1/conversations")).json()) as { id: string }[];
  for (const c of conversations) {
    await page.request.delete(`/api/v1/conversations/${c.id}`, { headers: { "X-CSRF-Token": csrf.csrf_token } });
  }
}

async function closeSheet(page: Page) {
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
}

async function ask(page: Page, question: string) {
  const composer = page.getByLabel("Ask a question about your documents");
  await composer.fill(question);
  await composer.press("Enter");
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });

  test("capture desktop screens", async ({ page }) => {
    mkdirSync(path.join(OUT!, "raw"), { recursive: true });
    await page.goto("/");
    await snap(page, "01-landing-hero");
    await snap(page, "02-landing-full-page", true);

    await signIn(page);
    await clearConversations(page);
    await page.goto("/knowledge-base");
    await expect(page.getByText(/Reading|Indexing|Embedding|Queued/)).toHaveCount(0, { timeout: 90_000 });
    await snap(page, "04-knowledge-base");

    await page.getByRole("link", { name: "Northwind Handbook" }).first().click();
    await expect(page.getByText("Indexed passages")).toBeVisible();
    await page.waitForLoadState("networkidle");
    await snap(page, "05-document-detail");

    await page.goto("/chat");
    await ask(page, "How many days of annual leave do new employees get, and do unused days carry over?");
    let answer = page.locator("article").last();
    await expect(answer.getByRole("button", { name: /^Source \d+:/ }).first()).toBeVisible({ timeout: 60_000 });
    await snap(page, "06-chat-answer");

    await answer.getByRole("button", { name: "Why this answer?" }).click();
    await expect(page.getByRole("dialog").getByRole("heading", { name: "Relevance check" })).toBeVisible();
    await snap(page, "08-answer-trace");
    await closeSheet(page);

    await ask(page, "How much does express shipping to Germany cost, and how long does it take?");
    answer = page.locator("article").last();
    const pdfChip = answer.getByRole("button", { name: /^Source \d+: Shipping Rates/ }).first();
    await expect(pdfChip).toBeVisible({ timeout: 60_000 });
    await pdfChip.click();
    await expect(page.getByRole("dialog").locator("mark.cb-hl").first()).toBeVisible();
    await snap(page, "07-source-viewer-pdf");
    await closeSheet(page);

    await ask(page, "What is our policy on company cars?");
    await expect(page.getByText(/couldn.t find sufficient information/).last()).toBeVisible({ timeout: 60_000 });
    await snap(page, "09-honest-refusal");

    await page.goto("/unanswered");
    await expect(page.getByRole("cell", { name: "What is our policy on company cars?" }).first()).toBeVisible();
    await snap(page, "10-unanswered-questions");

    await page.goto("/dashboard");
    await expect(page.getByText("Questions, last 7 days")).toBeVisible();
    await snap(page, "03-dashboard");
  });
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });

  test("capture phone screens", async ({ page }) => {
    await page.goto("/");
    await snap(page, "11-phone-landing");
    await signIn(page);
    await clearConversations(page);
    await page.goto("/chat");
    await ask(page, "How long do I have to return an item?");
    await expect(page.locator("article").last().getByRole("button", { name: /^Source \d+:/ }).first()).toBeVisible({
      timeout: 60_000,
    });
    await snap(page, "12-phone-chat");
  });
});

/* ---- Framed showcase images ---------------------------------------------------------- */

const SHOWCASE = [
  { file: "01-landing-hero", name: "00-cover", title: "AI knowledge base with verifiable citations", sub: "Upload documents. Ask in plain language. Every answer links to the exact page." },
  { file: "06-chat-answer", name: "01-cited-answers", title: "Answers with sources you can check", sub: "Streaming answers; every claim cites a passage from your own documents." },
  { file: "07-source-viewer-pdf", name: "02-source-viewer", title: "One click to the exact passage", sub: "Citations open the original PDF with the passage highlighted." },
  { file: "09-honest-refusal", name: "03-honest-refusal", title: "Honest when it doesn't know", sub: "No relevant passage means no guessing; the gap is logged for follow-up." },
  { file: "08-answer-trace", name: "04-answer-trace", title: "Why this answer?", sub: "Admins see retrieval scores, relevance thresholds, tokens and cost." },
  { file: "04-knowledge-base", name: "05-knowledge-base", title: "A knowledge base that indexes itself", sub: "PDF, Word, Markdown and text; scanned files are flagged, not silently skipped." },
  { file: "03-dashboard", name: "06-dashboard", title: "Usage and quality at a glance", sub: "Questions asked, unanswered gaps, helpful rate and AI usage per workspace." },
];

// The real logo mark (same file the browser uses as its icon).
const LOGO = `data:image/svg+xml;base64,${readFileSync(path.join(process.cwd(), "app/icon.svg")).toString("base64")}`;

const STACK = ["Next.js 16", "FastAPI", "Postgres + pgvector", "Hybrid RAG", "SSE streaming", "Row-level security"];

function frameHtml(title: string, sub: string, image: string, w: number, h: number) {
  const wide = w / h > 1.5;
  return `<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0}
body{width:${w}px;height:${h}px;overflow:hidden;font-family:Inter,system-ui,sans-serif;color:#fff;
 background:radial-gradient(circle at 12% 18%,rgba(20,184,166,.28),transparent 42%),radial-gradient(circle at 88% 85%,rgba(34,211,238,.18),transparent 45%),linear-gradient(135deg,#061128,#0b1b33 55%,#12284a);
 display:flex;flex-direction:column;padding:${wide ? 40 : 44}px ${wide ? 56 : 48}px 0}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:24px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:20px;color:#e4ebf5}
.brand img{width:30px;height:30px;display:block}
h1{font-size:${wide ? 40 : 42}px;line-height:1.12;font-weight:700;letter-spacing:-.02em;margin-top:${wide ? 14 : 22}px;max-width:${wide ? 900 : 860}px}
p{font-size:${wide ? 19 : 20}px;color:#c9d4e5;margin-top:10px;max-width:820px;line-height:1.45}
.chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end;max-width:${wide ? 420 : 330}px}
.chips span{font-size:13px;font-weight:600;padding:6px 11px;border-radius:999px;background:rgba(255,255,255,.08);color:#ccfbf1;border:1px solid rgba(20,184,166,.35)}
.win{margin-top:${wide ? 24 : 30}px;flex:1;border-radius:14px 14px 0 0;overflow:hidden;background:#fff;box-shadow:0 30px 80px -20px rgba(0,0,0,.6),0 0 0 1px rgba(255,255,255,.08)}
.bar{height:30px;background:#eef2f7;display:flex;align-items:center;gap:7px;padding:0 14px}
.bar b{width:11px;height:11px;border-radius:50%;background:#d5dde8}
.win img{display:block;width:100%}
</style></head><body>
<div class="top"><div><div class="brand"><img src="${LOGO}" alt="">CiteBase</div><h1>${title}</h1><p>${sub}</p></div>
<div class="chips">${STACK.map((s) => `<span>${s}</span>`).join("")}</div></div>
<div class="win"><div class="bar"><b></b><b></b><b></b></div><img src="${image}"></div>
</body></html>`;
}

const FORMATS = [
  { dir: "upwork", width: 1000, height: 750 },
  { dir: "fiverr", width: 1280, height: 769 },
];

for (const format of FORMATS) {
  test.describe(`showcase ${format.dir}`, () => {
    test.use({ viewport: { width: format.width, height: format.height }, deviceScaleFactor: 2 });

    test(`compose ${format.dir} images`, async ({ page }) => {
      mkdirSync(path.join(OUT!, format.dir), { recursive: true });
      for (const item of SHOWCASE) {
        const data = `data:image/png;base64,${readFileSync(raw(item.file)).toString("base64")}`;
        await page.setContent(frameHtml(item.title, item.sub, data, format.width, format.height), {
          waitUntil: "networkidle",
        });
        await page.screenshot({ path: path.join(OUT!, format.dir, `${item.name}.png`) });
      }
    });
  });
}
