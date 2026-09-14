import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, gotoAndSettle, test } from "./helpers";

const shotDir = resolve("e2e/artifacts/avatar-ui");

const stubAnswer = {
  type: "answer",
  answer: "A firewall filters network traffic between trust zones.",
  walkthrough: false,
  retrieved: [],
  cve_matches: [
    {
      cve_id: "CVE-2024-0001",
      severity: "HIGH",
      matched_value: "nginx",
      summary: "Example curated match for UI verification.",
    },
  ],
  disclaimer:
    "Advisory only — not a substitute for a professional security assessment.",
};

test.beforeAll(() => {
  mkdirSync(shotDir, { recursive: true });
});

test("login error is human-readable (no raw JSON)", async ({ guestPage: page }) => {
  await gotoAndSettle(page, "/login");
  await page.locator('input[type="email"]').fill("nobody@example.com");
  await page.locator('input[type="password"]').fill("wrong-password");
  await page.getByRole("button", { name: /sign in/i }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  const text = await alert.innerText();
  expect(text.toLowerCase()).not.toContain("invalid_credentials");
  expect(text).not.toMatch(/\{.*"detail"/);
  expect(text.toLowerCase()).toMatch(/incorrect|password|try again/);
  await page.screenshot({ path: resolve(shotDir, "login-error.png"), fullPage: true });
});

test("customer avatar chat + menu sign-out", async ({ customerPage: page }) => {
  // Stub Q&A so UI verification is not blocked by provider key health.
  await page.route("**/api/smb/qa/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(stubAnswer),
    });
  });

  await gotoAndSettle(page, "/chat");
  await expect(page.locator(".assistant-page")).toBeVisible();
  await expect(page.locator(".figure-img")).toBeVisible();
  await expect(page.locator(".assistant-composer")).toBeVisible();
  await expect(page.getByRole("button", { name: /attach file/i })).toBeDisabled();

  await page.screenshot({ path: resolve(shotDir, "avatar-desktop.png"), fullPage: true });

  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({ path: resolve(shotDir, "avatar-mobile-375.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });

  await page.getByLabel("Ask AEGIS").fill("What is a firewall in one sentence?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator(".exchange").first()).toBeVisible();
  await expect(page.locator(".disclaimer").first()).toBeVisible();
  await expect(page.locator(".cite").first()).toContainText("CVE-2024-0001");
  await page.screenshot({ path: resolve(shotDir, "avatar-with-answer.png"), fullPage: true });

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.waitForURL(/\/(?:\?.*)?$/);
  const me = await page.request.get("/api/smb/auth/me");
  expect(me.ok()).toBeTruthy();
  const body = (await me.json()) as { role: string };
  expect(body.role).toBe("guest");
});

test("ask failure shows FormError (no raw dump)", async ({ customerPage: page }) => {
  await page.route("**/api/smb/qa/ask", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "model-router chat HTTP 401" }),
    });
  });
  await gotoAndSettle(page, "/chat");
  await page.getByLabel("Ask AEGIS").fill("trigger error");
  await page.getByRole("button", { name: "Send" }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert).toContainText(/something went wrong|try again/i);
  await page.screenshot({ path: resolve(shotDir, "ask-error.png"), fullPage: true });
});

test("composer 'sign me out' clears session", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  const email = `e2e-so-${Date.now()}@example.com`;
  const password = "secure-pass-123";
  const slug = `e2e-so-${Date.now().toString(36)}`;
  const resp = await page.request.post("/api/smb/auth/register", {
    data: { email, password, slug },
  });
  expect(resp.ok(), await resp.text()).toBeTruthy();

  await gotoAndSettle(page, "/chat");
  await page.getByLabel("Ask AEGIS").fill("sign me out");
  await page.getByRole("button", { name: "Send" }).click();
  await page.waitForURL(/\/(?:\?.*)?$/);
  const me = await page.request.get("/api/smb/auth/me");
  const body = (await me.json()) as { role: string };
  expect(body.role).toBe("guest");
  await context.close();
});
