/**
 * Live production verification against https://defenseaegis.org
 * Run: npx playwright test e2e/live-avatar-deploy.spec.ts --config=playwright.live.config.ts
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

const shotDir = resolve("e2e/artifacts/live-avatar-deploy");
const BASE = process.env.SMB_PORTAL_BASE_URL ?? "https://defenseaegis.org";

test.beforeAll(() => {
  mkdirSync(shotDir, { recursive: true });
});

test("live avatar walkthrough: ask, menu sign-out, sign-me-out", async ({
  browser,
}) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({
    baseURL: BASE,
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();
  const email = `live-avatar-${Date.now()}@example.com`;
  const password = "secure-pass-123";
  const slug = `live-av-${Date.now().toString(36)}`;
  const transcript: string[] = [];

  function log(msg: string) {
    transcript.push(`${new Date().toISOString()} ${msg}`);
    console.log(msg);
  }

  // --- restyled login error ---
  await page.goto(`/login?cb=${Date.now()}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".auth-card")).toBeVisible({ timeout: 30_000 });
  await page.locator('input[type="email"]').fill("nobody@example.com");
  await page.locator('input[type="password"]').fill("wrong-password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("alert")).toContainText(/incorrect|password|try again/i);
  await page.screenshot({ path: resolve(shotDir, "01-login-error.png"), fullPage: true });
  log("PASS login error human-readable");

  // --- register via API on public domain ---
  const reg = await page.request.post("/api/smb/auth/register", {
    data: { email, password, slug },
  });
  expect(reg.ok(), await reg.text()).toBeTruthy();
  log(`PASS registered ${email}`);

  // Seed inventory so answers can ground + cite CVE matches when available
  const intake = await page.request.post("/api/smb/onboarding/intake", {
    data: {
      answers: [
        {
          category: "database",
          value: "PostgreSQL 16",
        },
      ],
    },
  });
  log(`intake status=${intake.status()} body=${(await intake.text()).slice(0, 200)}`);

  await page.goto(`/chat?cb=${Date.now()}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".assistant-page")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".figure-img")).toBeVisible();
  await page.screenshot({ path: resolve(shotDir, "02-avatar-desktop.png"), fullPage: true });
  log("PASS avatar screen visible");

  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({ path: resolve(shotDir, "03-avatar-mobile-375.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });
  log("PASS mobile 375 screenshot");

  // Real ask
  const question =
    "I run PostgreSQL 16 — what should I check first for database security, in two short sentences?";
  await page.getByLabel("Ask AEGIS").fill(question);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator(".exchange").first()).toBeVisible({ timeout: 120_000 });
  await expect(page.locator(".disclaimer").first()).toBeVisible();
  const answerText = await page.locator(".exchange .bubble.ai").first().innerText();
  expect(answerText.length).toBeGreaterThan(40);
  expect(answerText.toLowerCase()).not.toContain("something went wrong");
  await page.screenshot({ path: resolve(shotDir, "04-avatar-with-answer.png"), fullPage: true });
  log(`PASS real answer (${answerText.length} chars)`);
  log(`ANSWER_SNIPPET: ${answerText.slice(0, 400).replace(/\s+/g, " ")}`);

  // Menu sign-out
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.waitForURL(/defenseaegis\.org\/?(?:\?.*)?$/);
  const me1 = await page.request.get("/api/smb/auth/me");
  const body1 = (await me1.json()) as { role: string };
  expect(body1.role).toBe("guest");
  await page.screenshot({ path: resolve(shotDir, "05-after-menu-signout.png"), fullPage: true });
  log("PASS menu sign-out → guest");

  // Sign back in
  await page.goto(`/login?cb=${Date.now()}`, { waitUntil: "domcontentloaded" });
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".assistant-page")).toBeVisible({ timeout: 30_000 });
  log("PASS signed back in");

  // Composer "sign me out"
  await page.getByLabel("Ask AEGIS").fill("sign me out");
  await page.getByRole("button", { name: "Send" }).click();
  await page.waitForURL(/defenseaegis\.org\/?(?:\?.*)?$/);
  const me2 = await page.request.get("/api/smb/auth/me");
  const body2 = (await me2.json()) as { role: string };
  expect(body2.role).toBe("guest");
  await page.screenshot({ path: resolve(shotDir, "06-after-composer-signout.png"), fullPage: true });
  log("PASS composer 'sign me out' → guest");

  // Register page restyle
  await page.goto(`/register?cb=${Date.now()}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".auth-card")).toBeVisible();
  await page.screenshot({ path: resolve(shotDir, "07-register-restyled.png"), fullPage: true });
  log("PASS register restyled");

  writeFileSync(resolve(shotDir, "transcript.txt"), transcript.join("\n") + "\n");
  await context.close();
});
