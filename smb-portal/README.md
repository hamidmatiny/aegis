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

## Compose

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

## Pages

| Route | Purpose |
|-------|---------|
| `/onboarding` | Register + intake form → `/onboarding/*` |
| `/chat` | Free Q&A → `POST /qa/ask` with mandatory disclaimer per answer |
| `/walkthrough` | Paid walkthrough request / upsell paywall |
| `/billing` | `GET /billing/usage` chart + visible discrepancies |

## Known limitations

- API key is stored in `sessionStorage` for demo convenience — not a production secret vault.
- Walkthrough upgrade still requires an operator to flip the tenant’s policy-engine override.
