import { defineConfig, devices } from "@playwright/test";

/**
 * Golden-path smoke test against a running stack (default: the dev stack behind Caddy).
 * It uses the real configured AI provider, so it needs a provider key and costs a fraction of
 * a cent per run. Run it with the official Playwright image (see README, "End-to-end test").
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "./tests/e2e/.results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
