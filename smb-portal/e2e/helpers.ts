import { test as base, expect, type Browser, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

type RoleFixtures = {
  guestPage: Page;
  customerPage: Page;
  adminPage: Page;
};

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function loadEnvFile(): Record<string, string> {
  const out: Record<string, string> = {};
  try {
    const raw = readFileSync(resolve(__dirname, "../../.env"), "utf8");
    for (const line of raw.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eq = trimmed.indexOf("=");
      if (eq < 0) continue;
      let val = trimmed.slice(eq + 1).trim();
      if (
        (val.startsWith("'") && val.endsWith("'")) ||
        (val.startsWith('"') && val.endsWith('"'))
      ) {
        val = val.slice(1, -1);
      }
      out[trimmed.slice(0, eq)] = val;
    }
  } catch {
    /* optional */
  }
  return out;
}

const fileEnv = loadEnvFile();
const ADMIN_USER =
  process.env.ADMIN_USERNAME || fileEnv.ADMIN_USERNAME || "smbadmin";
const ADMIN_PASS =
  process.env.ADMIN_PASSWORD || fileEnv.ADMIN_PASSWORD || "";

async function waitSettled(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  // AuthProvider finishes /auth/me before clearing loading.
  await expect(page.locator("text=Loading").first())
    .toHaveCount(0, { timeout: 15_000 })
    .catch(() => undefined);
}

async function gotoAndSettle(page: Page, path: string) {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await waitSettled(page);
}

/**
 * Fresh browser context per role fixture — no shared cookies/sessionStorage.
 */
export const test = base.extend<RoleFixtures>({
  guestPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await use(page);
    await context.close();
  },

  customerPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
    const password = "secure-pass-123";
    const slug = `e2e-${Date.now().toString(36)}`;
    const resp = await page.request.post("/api/smb/auth/register", {
      data: { email, password, slug },
    });
    expect(resp.ok(), await resp.text()).toBeTruthy();
    await use(page);
    await context.close();
  },

  adminPage: async ({ browser }, use) => {
    test.skip(!ADMIN_PASS, "ADMIN_PASSWORD not set in env/.env");
    const context = await browser.newContext();
    const page = await context.newPage();
    const resp = await page.request.post("/api/smb/auth/admin-login", {
      data: { username: ADMIN_USER, password: ADMIN_PASS },
    });
    expect(resp.ok(), await resp.text()).toBeTruthy();
    await use(page);
    await context.close();
  },
});

export { expect, gotoAndSettle };

/** Assert final path after redirects settle. */
export async function expectPath(page: Page, path: string) {
  await expect(page).toHaveURL(new RegExp(`${path.replace(/\//g, "\\/")}(?:\\?.*)?$`));
}
