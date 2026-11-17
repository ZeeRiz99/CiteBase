import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const SHOTS = process.env.E2E_SCREENSHOTS; // optional folder for review screenshots

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
}

test("owner invites a viewer, who joins through the link", async ({ page, browser }) => {
  const stamp = Date.now();
  const ownerEmail = `owner-${stamp}@example.com`;
  const inviteeEmail = `viewer-${stamp}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Your name").fill("Olivia Owner");
  await page.getByLabel("Company or team (optional)").fill("Team Test Co");
  await page.getByLabel("Work email").fill(ownerEmail);
  await page.getByLabel("Password").fill("e2e-team-owner-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  // Invite from Settings; the one-time link is shown for copying.
  await page.goto("/settings");
  const team = page.locator("#team");
  await expect(team.getByText("Olivia Owner")).toBeVisible();
  await team.getByLabel("Invite by email").fill(inviteeEmail);
  await team.getByLabel("Role", { exact: true }).selectOption("viewer");
  await team.getByRole("button", { name: "Send invite" }).click();
  const link = await team.locator("code").innerText();
  expect(link).toContain("/invite?token=");
  await expect(team.getByText(inviteeEmail, { exact: true })).toBeVisible(); // pending list
  await shot(page, "team-settings-owner");

  // The invitee opens the link in a separate browser.
  const other = await browser.newContext();
  const guest = await other.newPage();
  await guest.goto(new URL(link).pathname + new URL(link).search);
  await expect(guest.getByRole("heading", { name: "Join Team Test Co" })).toBeVisible();
  await expect(guest.getByText("Olivia Owner invited you as viewer")).toBeVisible();
  await shot(guest, "team-invite-page");
  await guest.getByLabel("Your name").fill("Victor Viewer");
  await guest.getByLabel("Choose a password").fill("e2e-team-viewer-password");
  await guest.getByLabel("Confirm password").fill("e2e-team-viewer-password");
  await guest.getByRole("button", { name: "Accept and join" }).click();
  await expect(guest).toHaveURL(/\/dashboard/);

  // Viewers see no team management.
  await guest.goto("/settings");
  await expect(guest.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(guest.locator("#team")).toHaveCount(0);
  await other.close();

  // The owner now sees the new member and can change the role.
  await page.reload();
  await expect(team.getByText("Victor Viewer")).toBeVisible();
  await team.getByLabel("Role for Victor Viewer").selectOption("member");
  await expect(page.getByText("Victor Viewer is now member")).toBeVisible();
  await expect(team.getByText(inviteeEmail, { exact: true })).toHaveCount(0); // no longer pending
});
