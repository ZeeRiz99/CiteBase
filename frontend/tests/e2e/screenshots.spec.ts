import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * README screenshots from the labeled demo workspace (fictional DEMO DATA, `app.cli seed`).
 * Runs only when DEMO_PASSWORD and E2E_SCREENSHOTS are set; see docs/ASSET_BRIEF.md.
 */
const PASSWORD = process.env.DEMO_PASSWORD;
const OUT = process.env.E2E_SCREENSHOTS;

test.skip(!PASSWORD || !OUT, "set DEMO_PASSWORD and E2E_SCREENSHOTS to capture README screenshots");

async function capture(page: Page, name: string) {
  await page.waitForTimeout(400); // let transitions finish
  await page.screenshot({ path: path.join(OUT!, `${name}.png`) });
}

async function closeSheet(page: Page) {
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
}

test("capture README screenshots", async ({ page }) => {
  await page.goto("/");
  await capture(page, "landing");

  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.DEMO_EMAIL ?? "demo@example.com");
  await page.getByLabel("Password").fill(PASSWORD!);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.goto("/knowledge-base");
  await expect(page.getByText("Ready", { exact: true }).first()).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText(/Reading|Indexing|Embedding|Queued/)).toHaveCount(0, { timeout: 90_000 });
  await capture(page, "knowledge-base");

  await page.goto("/chat");
  const composer = page.getByLabel("Ask a question about your documents");
  await composer.fill("How many days of annual leave do new employees get, and do unused days carry over?");
  await composer.press("Enter");
  const answer = page.locator("article").last();
  await expect(answer.getByRole("button", { name: /^Source \d+:/ }).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, "chat-answer");

  const pdfChip = answer.getByRole("button", { name: /^Source \d+: Northwind Handbook/ }).first();
  const chip = (await pdfChip.count()) ? pdfChip : answer.getByRole("button", { name: /^Source \d+:/ }).first();
  await chip.click();
  await expect(page.getByRole("dialog").locator("mark").first()).toBeVisible();
  await capture(page, "source-viewer");
  await closeSheet(page);

  await answer.getByRole("button", { name: "Why this answer?" }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Relevance check" })).toBeVisible();
  await capture(page, "answer-trace");
  await closeSheet(page);

  await composer.fill("What is our policy on company cars?");
  await composer.press("Enter");
  await expect(page.getByText(/couldn.t find sufficient information/).last()).toBeVisible({ timeout: 60_000 });
  await capture(page, "chat-refusal");

  await page.goto("/unanswered");
  await expect(page.getByRole("cell", { name: "What is our policy on company cars?" }).first()).toBeVisible();
  await capture(page, "unanswered");

  await page.goto("/dashboard");
  await expect(page.getByText("Questions, last 7 days")).toBeVisible();
  await capture(page, "dashboard");
});
