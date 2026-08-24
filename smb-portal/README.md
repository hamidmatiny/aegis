# AEGIS SMB Portal

Customer-facing React + Vite UI for the **AEGIS-for-SMB Phase 1 MVP**: onboarding,
free-tier Q&A with a mandatory per-answer disclaimer, paid-walkthrough paywall,
and an audit-backed usage chart.

This app talks only to [`smb-copilot`](../smb-copilot/README.md) (proxied as
`/api/smb/*`). It is **separate from** [`dashboard/`](../dashboard/README.md) —
same React/Vite tooling versions, different product surface (customer helpdesk
vs operator ops).

Part of the [AEGIS](../README.md) monorepo. Pre-revenue MVP: no live paying
customers; the walkthrough “upgrade” still requires an operator to flip the
tenant’s policy-engine CEL override.

## Install / run (standalone)

```bash
cd smb-portal
npm install
npm run dev      # http://127.0.0.1:3001 (proxies /api/smb → smb-copilot :8093)
```

Requires smb-copilot (and its dependencies) listening on `:8093`. For a full
stack from the repo root, prefer compose below.

## Compose

```bash
# from repo root
cp .env.example .env   # if needed
docker compose up -d --build smb-copilot smb-portal
# Portal: http://127.0.0.1:3001
```

## Environment

| Variable | Purpose |
|----------|---------|
| `SMB_PORTAL_PORT` | Host publish port in compose (default `3001`) |

Browser calls go to `/api/smb/*`; nginx (compose) or Vite (dev) proxies to
smb-copilot. The tenant API key is sent as `Authorization: Bearer <key>` from
`sessionStorage` after onboarding.

## Pages

| Route | Purpose |
|-------|---------|
| `/onboarding` | Register + intake form → `/onboarding/*` |
| `/chat` | Free Q&A → `POST /qa/ask` with mandatory disclaimer per answer |
| `/walkthrough` | Paid walkthrough request / upsell paywall |
| `/billing` | `GET /billing/usage` chart + visible discrepancies |

## Tests / checks

There is no separate unit-test suite yet. Local verification:

```bash
cd smb-portal
npm run lint
npm run build
```

## Known limitations

- API key is stored in `sessionStorage` for demo convenience — not a production
  secret vault.
- Walkthrough upgrade still requires an operator to flip the tenant’s
  policy-engine override.
- Usage discrepancies from smb-copilot are shown in the UI; they are never
  silently reconciled.
