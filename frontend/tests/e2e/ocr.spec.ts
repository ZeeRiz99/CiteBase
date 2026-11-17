import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const SAMPLES = path.resolve(__dirname, "../../../samples");
const SHOTS = process.env.E2E_SCREENSHOTS;

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

async function ask(page: Page, question: string) {
  const composer = page.getByLabel("Ask a question about your documents");
  await composer.fill(question);
  await composer.press("Enter");
}

test("scans and photos are read with text recognition and cited", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Oscar Reader");
  await page.getByLabel("Work email").fill(`ocr-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("e2e-text-recognition");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  // 1. Upload an image-only PDF and a JPEG photo; both become Ready with an OCR tag.
  await page.goto("/knowledge-base");
  await page
    .locator('input[type="file"]')
    .setInputFiles([path.join(SAMPLES, "Scanned Notice.pdf"), path.join(SAMPLES, "Delivery Note.jpg")]);
  await expect(page.getByText("Ready", { exact: true })).toHaveCount(2, { timeout: 120_000 });
  await expect(page.getByTitle("Text read with text recognition")).toHaveCount(2);
  await shot(page, "ocr-01-knowledge-base");

  // 2. The document page reports recognition confidence.
  await page.getByRole("link", { name: "Scanned Notice" }).click();
  await expect(page.getByText("Text recognized from a scan")).toBeVisible();
  await expect(page.getByText(/The text of 2 pages was read with text recognition \(OCR\), average confidence \d+%/)).toBeVisible();
  await shot(page, "ocr-02-document");

  // 3. A fact that exists only as pixels in the scan is answered and cited.
  await page.getByRole("link", { name: "Chat" }).first().click();
  await ask(page, "When is the returns desk at the Leeds warehouse open?");
  const answer = page.locator("article").last();
  const chip = answer.getByRole("button", { name: /^Source \d+: Scanned Notice/ }).first();
  await expect(chip).toBeVisible({ timeout: 60_000 });
  await expect(answer).toContainText(/8:00/);
  await expect(answer).toContainText(/16:00/);

  // 4. The citation opens the scanned page with the recognized passage as text.
  await chip.click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByText(/This page is a scan/)).toBeVisible({ timeout: 30_000 });
  await expect(sheet.locator("mark").first()).toBeVisible();
  await shot(page, "ocr-03-scanned-source");
  await sheet.getByRole("button", { name: "Close" }).click();
  await expect(sheet).toBeHidden();

  // 5. The photo: answer, citation, and the image shown in the viewer.
  await ask(page, "How many Summit Tents were delivered to the Harbour Street store?");
  const second = page.locator("article").last();
  const photoChip = second.getByRole("button", { name: /^Source \d+: Delivery Note/ }).first();
  await expect(photoChip).toBeVisible({ timeout: 60_000 });
  await expect(second).toContainText(/6 Summit Tents/);
  await photoChip.click();
  await expect(page.getByRole("dialog").getByRole("img", { name: /Original image: Delivery Note/ })).toBeVisible();
  await shot(page, "ocr-04-photo-source");
});
