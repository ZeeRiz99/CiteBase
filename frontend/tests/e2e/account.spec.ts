import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { emailedLink, registerConfirmed } from "./helpers";

const SHOTS = process.env.E2E_SCREENSHOTS;

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

test("uploads wait for a confirmed email; the sign-in email can be changed", async ({ page }) => {
  const stamp = Date.now();
  const first = `first-${stamp}@example.com`;
  const second = `second-${stamp}@example.com`;
  const password = "e2e-account-password";

  // Unconfirmed: the knowledge base asks to confirm instead of accepting files.
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Cam Change");
  await page.getByLabel("Work email").fill(`unconfirmed-${stamp}@example.com`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await page.goto("/knowledge-base");
  await expect(page.getByText(/Confirm your email to upload documents/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Choose files" })).toBeDisabled();
  await shot(page, "account-01-unconfirmed");
  await page.context().clearCookies(); // sign out

  // Confirmed account changes its email: link to the new inbox, then sign in with it.
  await registerConfirmed(page, "Cam Change", first, password);
  await page.goto("/settings");
  const card = page.locator("#email");
  await card.getByLabel("New email").fill(second);
  await card.getByLabel("Current password").fill(password);
  const requested = Date.now() - 1000;
  await card.getByRole("button", { name: "Send confirmation link" }).click();
  await expect(card.getByText(`We sent a confirmation link to ${second}`)).toBeVisible();
  await shot(page, "account-02-change-requested");

  await page.goto(await emailedLink(second, "/confirm-email-change", requested));
  await expect(page.getByRole("heading", { name: "Email changed" })).toBeVisible();
  await shot(page, "account-03-changed");

  await page.goto("/login");
  await page.getByLabel("Email").fill(second);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await page.goto("/settings");
  await expect(page.locator("#email").getByText(`${second}`).first()).toBeVisible();
});
