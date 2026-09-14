# AEGIS SMB Portal

Customer-facing frontend for SMB Copilot (onboarding, Q&A, walkthrough paywall, usage).

Separate from `dashboard/` — same React/Vite tooling versions, different app.

## Install / run

```bash
cd smb-portal
npm install
npm run dev      # http://127.0.0.1:3001 (proxies /api/smb → smb-copilot :8093)
npm run build
npm run lint
```

## E2E (route guards)

Requires smb-copilot on `:8093` and `ADMIN_PASSWORD` in the repo-root `.env` for admin cells.

```bash
cd smb-portal
npx playwright install chromium   # once
npm run test:e2e
```

Each test case uses a **fresh browser context** (no shared cookies). See `e2e/route-guards.spec.ts`.

## Brand

Refined dark navy landing (`#0a0f1a` paper) with Plus Jakarta Sans, security-blue accents, and verified-green used sparingly for trust checks. Primary CTAs use solid blue `#1d4ed8` for WCAG contrast on white label text. Favicons + `public/og-image.png` for share previews.

Post-login `/chat` uses an avatar-first shell (`AegisAvatar` + composer): ambient rings/halo animate; the robot image stays still and is swappable via `/assistant/aegis-robot.png`. Attach is disabled until a backend exists; mic uses browser SpeechRecognition into the composer when available. “Sign me out” in the composer (or Account → Sign out) clears the session.

`nginx.conf` sends `Cache-Control: no-store` for the SPA shell (`index.html`) and long immutable cache for hashed `/assets/*`. Missing asset hashes return **404** (not the HTML shell) so a stale cached `index.html` cannot load HTML-as-JS after a deploy.

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Marketing landing (how it works, pricing, trust, footer) |
| `/privacy` | Privacy Policy |
| `/terms` | Terms of Use |
| `/login` / `/register` | Customer auth |
| `/onboarding` | Register + intake form → guest or account setup |
| `/chat` | Avatar-first Q&A → `POST /qa/ask` (disclaimer + CVE cites per answer) |
| `/walkthrough` | Paid walkthrough (same avatar UI) / upsell paywall |
| `/billing` | `GET /billing/usage` chart + visible discrepancies |

Pricing shown on `/` matches live Stripe `STRIPE_PRICE_ID_STANDARD` ($29 CAD/month as of 2026-09-14). Guided walkthroughs remain a paid Standard feature.

## Compose (production demo)

Root domain serves smb-portal directly (no `/smb/` prefix). API at `/api/smb/*`.

```bash
cp .env.example .env   # repo root
docker compose -f docker-compose.yml -f deploy/oracle/docker-compose.demo.yml up -d --build
# Portal: https://defenseaegis.org/ (or http://127.0.0.1 when testing locally)
```

## Compose (local dev stack)

```bash
cp .env.example .env   # repo root
docker compose up -d --build smb-copilot smb-portal
# Portal: http://127.0.0.1:3001
```

## Environment

| Variable | Purpose |
|----------|---------|
| `SMB_PORTAL_PORT` | Host publish port (default `3001`) |

Browser calls go to `/api/smb/*`; nginx (compose) or Vite (dev) proxies to smb-copilot. The tenant API key is sent as `Authorization: Bearer <key>` from session storage after onboarding.

## Known limitations

- API key is stored in `sessionStorage` for demo convenience — not a production secret vault.
- Walkthrough upgrade still requires an operator to flip the tenant’s policy-engine override.
- File attach is not wired (no upload API) — button stays disabled with an honest tooltip.
- Voice is browser dictation only (fills the question box); there is no server-side speech pipeline.
