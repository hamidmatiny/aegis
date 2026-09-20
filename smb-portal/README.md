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

Marketing landing (`/`) uses the persisted AEGIS design system in
`../design-system/aegis/MASTER.md` (navy `#0F172A`, CTA `#0369A1`, canvas
`#F8FAFC`, IBM Plex Sans) with a navy hero band and light body. The central
**How it works** block is the interception demo (App → AEGIS → Provider, four
scenarios, try-it-yourself against `POST /v1/chat/completions`). Evidence
screenshots: `../docs/landing-redesign/`.

In-product Q&A chrome stays dark navy with Plus Jakarta Sans; primary CTAs use
solid blue for contrast. Favicons + `public/og-image.png` for share previews.

Post-login `/chat` uses an avatar-first shell (`AegisAvatar` + composer): ambient rings/halo animate; the robot image stays still and is swappable via `/assistant/aegis-robot.png`. Attach is disabled until a backend exists; mic uses browser SpeechRecognition into the composer when available. “Sign me out” in the composer (or Account → Sign out) clears the session.

`nginx.conf` sends `Cache-Control: no-store` for the SPA shell (`index.html`) and long immutable cache for hashed `/assets/*`. Missing asset hashes return **404** (not the HTML shell) so a stale cached `index.html` cannot load HTML-as-JS after a deploy.

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Marketing landing — hero, proof strip, interception how-it-works, features, pricing, trust, footer |
| `/guides/smb-cve-exposure-checklist` | Public SEO guide — SMB CVE exposure checklist (aegis-growth). Build emits a route-specific HTML shell so `<title>` / canonical match the guide (not the homepage). |
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
| `CF_WEB_ANALYTICS_TOKEN` | Optional Cloudflare Web Analytics site token — injected into HTML at container start |

**Pageview + funnel analytics (Growth baseline):** the portal injects a first-party beacon to `POST /api/smb/analytics/collect` on hard HTML loads, and the React app posts SPA `pageview` + funnel-stage events (`signup_started`, `walkthrough_viewed`, `upgrade_viewed`, …). Server also emits `signup_completed`, `inventory_saved`, `qa_asked`, `cve_match_shown`, `upgrade_started`, `upgrade_completed`. Aggregate reads: `GET /api/smb/analytics/summary?days=7` with `Authorization: Bearer $CORP_READONLY_TOKEN` — response includes `by_path` pageviews **and** a `funnel.stages[]` block with counts + `conversion_from_previous`. Optional CF Web Analytics via `CF_WEB_ANALYTICS_TOKEN`.


## Known limitations

- API key is stored in `sessionStorage` for demo convenience — not a production secret vault.
- Walkthrough upgrade still requires an operator to flip the tenant’s policy-engine override.
- File attach is not wired (no upload API) — button stays disabled with an honest tooltip.
- Voice is browser dictation only (fills the question box); there is no server-side speech pipeline.
