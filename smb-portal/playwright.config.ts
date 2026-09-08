import { defineConfig, devices } from "@playwright/test";

/**
 * Route-guard E2E for smb-portal.
 * Requires smb-copilot on :8093 (docker compose). Portal is started by webServer.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.SMB_PORTAL_BASE_URL ?? "http://127.0.0.1:5173",
    trace: "on-first-retry",
    // Each test must create its own context — do not share storageState globally.
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5173",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
