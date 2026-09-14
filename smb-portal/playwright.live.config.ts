import { defineConfig, devices } from "@playwright/test";

/** Production-only config — no local webServer. */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "live-avatar-deploy.spec.ts",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 30_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.SMB_PORTAL_BASE_URL ?? "https://defenseaegis.org",
    trace: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
