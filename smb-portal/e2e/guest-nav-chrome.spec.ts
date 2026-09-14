import { test, expect, gotoAndSettle, expectPath } from "./helpers";

/**
 * After guest onboarding → /chat:
 * - /onboarding keeps the product sidebar (Guest · slug)
 * - /chat uses avatar-first chrome (no marketing Sign up; account menu shows Guest)
 */
test("guest onboarding then chat uses avatar chrome, not marketing Sign up", async ({
  guestPage,
}) => {
  const slug = `navfix-${Date.now().toString(36)}`;

  await gotoAndSettle(guestPage, "/onboarding");
  await guestPage.locator('input[placeholder="acme-bakery"]').fill(slug);
  await guestPage.getByRole("button", { name: /^Continue as guest$/i }).click();

  await expect(guestPage.locator(".sidebar-user")).toContainText(/Guest/i, {
    timeout: 30_000,
  });
  await expect(guestPage.locator(".sidebar-user strong")).toHaveText(slug);
  await expect(guestPage.locator(".marketing-nav")).toHaveCount(0);

  await expect(
    guestPage.getByRole("heading", { name: /What does your business run on/i }),
  ).toBeVisible({ timeout: 15_000 });

  await guestPage.getByPlaceholder(/PostgreSQL/i).fill("PostgreSQL 16");
  await guestPage.getByRole("button", { name: /Save and continue/i }).click();
  await expect(guestPage.getByText(/Profile saved/i)).toBeVisible({ timeout: 30_000 });

  await guestPage.getByRole("button", { name: /Go to Q&A/i }).click();
  await expectPath(guestPage, "/chat");

  await expect(guestPage.locator(".assistant-page")).toBeVisible();
  await expect(guestPage.locator(".marketing-nav")).toHaveCount(0);
  await expect(guestPage.locator(".sidebar")).toHaveCount(0);
  await expect(guestPage.getByRole("link", { name: /^Sign up$/i })).toHaveCount(0);

  await guestPage.getByRole("button", { name: "Account menu" }).click();
  await expect(guestPage.locator(".menu-panel")).toContainText(new RegExp(`Guest · ${slug}`));
});
