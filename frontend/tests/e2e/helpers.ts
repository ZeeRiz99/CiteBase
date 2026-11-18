import { expect, type Page } from "@playwright/test";

/** Mailpit (development email catcher) API. Every email the app sends lands there. */
const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";

type MailpitSearch = { messages: { ID: string; Created: string }[] };

/** Path and query of the newest link to `path` emailed to `to`, waiting up to 30 s for it. */
export async function emailedLink(to: string, path: string, after = 0): Promise<string> {
  const query = encodeURIComponent(`to:"${to}"`);
  for (let attempt = 0; attempt < 60; attempt++) {
    const found = (await (await fetch(`${MAILPIT}/api/v1/search?query=${query}&limit=10`)).json()) as MailpitSearch;
    for (const item of found.messages ?? []) {
      if (Date.parse(item.Created) < after) continue;
      const message = (await (await fetch(`${MAILPIT}/api/v1/message/${item.ID}`)).json()) as { Text: string };
      const match = message.Text.match(new RegExp(`https?://[^\\s]+(${path}\\?token=[A-Za-z0-9_-]+)`));
      if (match) return match[1];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`No email to ${to} with a ${path} link`);
}

/** Open the sign-up confirmation link, as the person would from their inbox. */
export async function confirmEmail(page: Page, email: string) {
  await page.goto(await emailedLink(email, "/verify-email"));
  await expect(page.getByRole("heading", { name: "Email confirmed" })).toBeVisible();
}

/** Register through the UI, then confirm the email. Lands on the dashboard. */
export async function registerConfirmed(page: Page, name: string, email: string, password: string, company?: string) {
  await page.goto("/register");
  await page.getByLabel("Your name").fill(name);
  if (company) await page.getByLabel("Company or team (optional)").fill(company);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await confirmEmail(page, email);
  await page.goto("/dashboard");
}
