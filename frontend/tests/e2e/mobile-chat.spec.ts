import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const SAMPLES = path.resolve(__dirname, "../../../samples");
const SHOTS = process.env.E2E_SCREENSHOTS;

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

test("chat works at phone width: tabs, answer, sources, passage", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Mo Bile");
  await page.getByLabel("Work email").fill(`mobile-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("e2e-mobile-chat-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.goto("/knowledge-base");
  await page.locator('input[type="file"]').setInputFiles(path.join(SAMPLES, "Returns Policy.md"));
  await expect(page.getByText("Ready", { exact: true })).toHaveCount(1, { timeout: 90_000 });
  await noHorizontalScroll(page);

  await page.goto("/chat");
  const tabs = page.getByRole("tablist", { name: "Chat panels" });
  await expect(tabs.getByRole("tab", { name: "Answer" })).toHaveAttribute("aria-selected", "true");
  await noHorizontalScroll(page);

  const composer = page.getByLabel("Ask a question about your documents");
  await composer.fill("How many days do I have to return a regular item?");
  await composer.press("Enter");
  const answer = page.locator("article").last();
  await expect(answer.getByRole("button", { name: /^Source \d+: Returns Policy/ }).first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(answer).toContainText(/30 days/);
  await noHorizontalScroll(page);
  await shot(page, "mobile-01-answer");

  // Sources tab lists the passages; opening one shows the highlighted passage.
  await tabs.getByRole("tab", { name: "Sources" }).click();
  const source = page.getByRole("button", { name: /Returns Policy/ }).first();
  await expect(source).toBeVisible();
  await noHorizontalScroll(page);
  await shot(page, "mobile-02-sources");
  await source.click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.locator("mark").first()).toBeVisible();
  await noHorizontalScroll(page);
  await shot(page, "mobile-03-passage");
  await sheet.getByRole("button", { name: "Close" }).click();

  // Chats tab shows the conversation list.
  await tabs.getByRole("tab", { name: "Chats" }).click();
  const item = page.getByRole("navigation", { name: "Conversations" }).getByRole("button", { name: /^How many days/ });
  await expect(item).toBeVisible();
  // Touch screens have no hover: the actions button must be visible.
  await expect(page.getByRole("button", { name: /Actions for How many days/ })).toHaveCSS("opacity", "1");
  await shot(page, "mobile-04-chats");
  await noHorizontalScroll(page);
});
