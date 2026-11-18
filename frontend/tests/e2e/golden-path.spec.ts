import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { registerConfirmed } from "./helpers";

const SAMPLES = path.resolve(__dirname, "../../../samples");
const SHOTS = process.env.E2E_SCREENSHOTS; // optional folder for review screenshots

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: false });
}

// Click the sheet's own Close button (Escape can be taken by an open hover preview first).
async function closeSheet(page: Page) {
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
}

test("register, upload, ask, verify the citation, refuse off-topic", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  // Production builds send a Content-Security-Policy; any violation fails the test.
  const cspViolations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy/i.test(message.text())) cspViolations.push(message.text());
  });

  // 1. Create an account and confirm the email from the inbox (uploads wait for it).
  await registerConfirmed(page, "Erin Tester", email, "e2e-golden-path-password");

  // 2. Upload two sample documents and wait until both are indexed.
  await page.goto("/knowledge-base");
  await page
    .locator('input[type="file"]')
    .setInputFiles([path.join(SAMPLES, "Returns Policy.md"), path.join(SAMPLES, "Shipping Rates.pdf")]);
  await expect(page.getByText("Ready", { exact: true })).toHaveCount(2, { timeout: 90_000 });
  await shot(page, "01-knowledge-base");

  // 3. Ask a question the documents answer.
  await page.getByRole("link", { name: "Chat" }).first().click();
  await expect(page).toHaveURL(/\/chat$/);
  const composer = page.getByLabel("Ask a question about your documents");
  await composer.fill("How many days do I have to return a regular item?");
  await composer.press("Enter");
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/);

  const answer = page.locator("article").last();
  const chip = answer.getByRole("button", { name: /^Source \d+: Returns Policy/ }).first();
  await expect(chip).toBeVisible({ timeout: 60_000 });
  await expect(answer).toContainText(/30 days/);
  await expect(answer.getByText(/(Strong|Partial) evidence/)).toBeVisible();
  await shot(page, "02-answer");

  // 4. The citation opens the passage, highlighted.
  await chip.click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("heading", { name: /Returns Policy/ })).toBeVisible();
  // The passage may span several sections (one highlight each); one of them holds the rule.
  await expect(sheet.locator("mark", { hasText: /30 days/i })).toBeVisible();
  await shot(page, "03-source");
  await closeSheet(page);

  // 5. Rate the answer; the rating sticks after a reload.
  await answer.getByRole("button", { name: "Helpful", exact: true }).click();
  await expect(answer.getByRole("button", { name: "Remove rating" })).toBeVisible();

  // 5b. A PDF citation opens the page with the passage highlighted in the text layer.
  await composer.fill("How many days does express delivery to France take?");
  await composer.press("Enter");
  const pdfAnswer = page.locator("article").nth(1);
  const pdfChip = pdfAnswer.getByRole("button", { name: /^Source \d+: Shipping Rates/ }).first();
  await expect(pdfChip).toBeVisible({ timeout: 60_000 });
  await pdfChip.click();
  const pdfSheet = page.getByRole("dialog");
  await expect(pdfSheet.locator(".react-pdf__Page canvas")).toBeVisible();
  await expect(pdfSheet.locator("mark.cb-hl").first()).toBeVisible();
  await shot(page, "03b-pdf-source");
  await closeSheet(page);

  // 6. An off-topic question is refused, not guessed.
  await composer.fill("Who won the football world cup in 1998?");
  await composer.press("Enter");
  await expect(
    page.getByText("I couldn't find sufficient information in your uploaded documents to answer this question reliably."),
  ).toBeVisible({ timeout: 60_000 });
  await shot(page, "04-refusal");

  // 7. History survives a reload: both questions are in the thread.
  await page.reload();
  const thread = page.getByRole("region", { name: "Conversation" });
  await expect(thread.getByText("How many days do I have to return a regular item?")).toBeVisible();
  await expect(thread.getByText(/couldn.t find sufficient information/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove rating" })).toBeVisible();

  // 8. The refusal is waiting in the admin's unanswered list.
  await page.goto("/unanswered");
  await expect(page.getByRole("cell", { name: "Who won the football world cup in 1998?" })).toBeVisible();

  expect(cspViolations).toEqual([]);
});
