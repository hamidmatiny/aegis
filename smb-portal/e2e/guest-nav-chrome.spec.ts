import { test, expect, gotoAndSettle, expectPath } from "./helpers";

/**
 * After guest onboarding → /chat, Layout must show authenticated sidebar
 * (Guest · {slug}), not marketing nav with Sign up.
 */
test("guest onboarding then chat shows Guest sidebar, not marketing Sign up", async ({
  guestPage,
}) => {
  const slug = `navfix-${Date.now().toString(36)}`;

  await gotoAndSettle(guestPage, "/onboarding");
  await guestPage.locator('input[placeholder="acme-bakery"]').fill(slug);
  await guestPage.getByRole("button", { name: /^Continue as guest$/i }).click();

  // Reactive chrome: sidebar Guest · slug must appear (and marketing Sign up gone)
  await expect(guestPage.locator(".sidebar-user")).toContainText(/Guest/i, {
    timeout: 30_000,
  });
  await expect(guestPage.locator(".sidebar-user strong")).toHaveText(slug);
  await expect(guestPage.locator(".marketing-nav")).toHaveCount(0);

  // Intake may show after remount (guest session re-hydrates registered)
  await expect(
    guestPage.getByRole("heading", { name: /What does your business run on/i }),
  ).toBeVisible({ timeout: 15_000 });

  await guestPage.getByPlaceholder(/PostgreSQL/i).fill("PostgreSQL 16");
  await guestPage.getByRole("button", { name: /Save and continue/i }).click();
  await expect(guestPage.getByText(/Profile saved/i)).toBeVisible({ timeout: 30_000 });

  await guestPage.getByRole("button", { name: /Go to Q&A/i }).click();
  await expectPath(guestPage, "/chat");

  const sidebarGuest =
    (await guestPage.locator(".sidebar-user").filter({ hasText: /Guest/i }).count()) > 0;
  const marketingSignUp = await guestPage
    .locator(".marketing-nav")
    .getByRole("link", { name: /Sign up/i })
    .count();
  const bodySnippet = (await guestPage.locator("body").innerText()).slice(0, 500);
  const evidence = {
    url: guestPage.url(),
    sidebarGuest,
    marketingSignUpCount: marketingSignUp,
    snippet: bodySnippet.replace(/\s+/g, " ").slice(0, 280),
  };
  console.log("GUEST_NAV_EVIDENCE", JSON.stringify(evidence));

  expect(evidence.sidebarGuest, JSON.stringify(evidence)).toBe(true);
  expect(evidence.marketingSignUpCount, JSON.stringify(evidence)).toBe(0);
  await expect(guestPage.locator(".sidebar-user")).toContainText(/Guest/i);
  await expect(guestPage.locator(".marketing-nav")).toHaveCount(0);
  await expect(guestPage.getByRole("link", { name: /^Sign up$/i })).toHaveCount(0);
});
