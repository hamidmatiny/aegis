import { test, expect, gotoAndSettle, expectPath } from "./helpers";

/**
 * Route-guard matrix — each cell uses a fresh browser context (see helpers).
 *
 * Expected destinations (render = stay on route):
 *
 * | Route          | Guest           | Customer        | Admin            |
 * |----------------|-----------------|-----------------|------------------|
 * | /              | render          | → /chat         | → /admin         |
 * | /login         | render          | → /chat         | → /admin         |
 * | /register      | render          | → /chat         | → /admin         |
 * | /onboarding    | render          | render          | render           |
 * | /chat          | → /login        | render          | → /admin         |
 * | /billing       | → /login        | render          | → /admin         |
 * | /admin/login   | render          | render          | → /admin         |
 * | /admin         | → /admin/login  | → /admin/login  | render           |
 */

const ROUTES = [
  "/",
  "/login",
  "/register",
  "/onboarding",
  "/chat",
  "/billing",
  "/admin/login",
  "/admin",
] as const;

test.describe("guest (clean context)", () => {
  for (const route of ROUTES) {
    test(`guest ${route}`, async ({ guestPage }) => {
      await gotoAndSettle(guestPage, route);
      switch (route) {
        case "/":
        case "/login":
        case "/register":
        case "/onboarding":
        case "/admin/login":
          await expectPath(guestPage, route === "/" ? "/" : route);
          break;
        case "/chat":
        case "/billing":
          await expectPath(guestPage, "/login");
          break;
        case "/admin":
          await expectPath(guestPage, "/admin/login");
          break;
      }
    });
  }
});

test.describe("customer (fresh registered session)", () => {
  for (const route of ROUTES) {
    test(`customer ${route}`, async ({ customerPage }) => {
      await gotoAndSettle(customerPage, route);
      switch (route) {
        case "/":
        case "/login":
        case "/register":
          await expectPath(customerPage, "/chat");
          break;
        case "/onboarding":
        case "/chat":
        case "/billing":
          await expectPath(customerPage, route);
          break;
        case "/admin/login":
          await expectPath(customerPage, "/admin/login");
          break;
        case "/admin":
          await expectPath(customerPage, "/admin/login");
          break;
      }
    });
  }
});

test.describe("admin (fresh operator session)", () => {
  for (const route of ROUTES) {
    test(`admin ${route}`, async ({ adminPage }) => {
      await gotoAndSettle(adminPage, route);
      switch (route) {
        case "/":
        case "/login":
        case "/register":
        case "/chat":
        case "/billing":
        case "/admin/login":
          await expectPath(adminPage, "/admin");
          break;
        case "/onboarding":
          // Intentionally unguarded (intake page has no role wrapper).
          await expectPath(adminPage, "/onboarding");
          break;
        case "/admin":
          await expectPath(adminPage, "/admin");
          break;
      }
    });
  }
});

test("guest landing shows AEGIS logo and signup CTA", async ({ guestPage }) => {
  await gotoAndSettle(guestPage, "/");
  await expect(guestPage.locator('img[src="/icon.svg"]').first()).toBeVisible();
  await expect(guestPage.getByRole("link", { name: /Sign up/i }).first()).toBeVisible();
  await expect(guestPage.getByRole("link", { name: /Continue as guest/i })).toBeVisible();
});
