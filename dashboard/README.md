# AEGIS Dashboard

React + TypeScript operations UI for monitoring defenses, editing policies, managing approvals, and searching audit logs.

## Features

| View | Data source | Description |
|------|-------------|-------------|
| **Attack Feed** | Audit `GET /v1/receipts` | Live feed of blocked/denied/escalated receipts with verify-on-click |
| **ASR Trends** | Red-team `GET /v1/campaigns` | Session bypass-rate charts per defense layer |
| **Policy Editor** | Policy-engine `GET /v1/policy-packs/{id}`, `POST /v1/dry-run` | YAML editor with CEL dry-run preview |
| **Tool Matrix** | Policy pack `tool_rules` | Read-only permission matrix for agent-gate |
| **Approvals** | Agent-gate `GET /v1/approvals`, `POST .../decide` | Human approval inbox |
| **Audit Log** | Audit query + export | Search by tenant/event/trace and export JSON |

The dashboard nginx container proxies backend APIs under `/api/*` to avoid CORS in production compose.

## Install and run

### Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build dashboard audit policy-engine agent-gate redteam

open http://localhost:3000
```

### Local dev (Vite)

Requires backend services on localhost (see root `docker compose up -d`).

```bash
cd dashboard
npm install
npm run dev
```

Vite dev server proxies `/api/audit`, `/api/policy`, `/api/agent-gate`, and `/api/redteam` to local service ports (see `vite.config.ts`).

### Production build

```bash
cd dashboard
npm install
npm run build
npm run preview
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DASHBOARD_PORT` | `3000` | Host port for dashboard nginx container |

Backend URLs are configured via nginx proxy in Docker or Vite proxy in local dev — no separate env vars required in the UI.

## API proxy paths

| Browser path | Upstream (compose network) |
|--------------|----------------------------|
| `/api/audit/*` | `audit:8084` |
| `/api/policy/*` | `policy-engine:8081` |
| `/api/agent-gate/*` | `agent-gate:8083` |
| `/api/redteam/*` | `redteam:8092` |

## New backend endpoints (Stage 9)

Added to support the dashboard:

| Service | Endpoint | Purpose |
|---------|----------|---------|
| policy-engine | `GET /v1/policy-packs/{id}` | Pack metadata + source YAML |
| policy-engine | `POST /v1/dry-run` | Validate draft YAML and preview decision |
| agent-gate | `GET /v1/approvals` | List pending (or all) approval requests |
| redteam | `GET /v1/campaigns` | List campaign summaries for ASR charts |

## E2E smoke test

```bash
./scripts/e2e-dashboard.sh
```

## Known limitations

| Gap | Status | Notes |
|-----|--------|-------|
| **Policy persist from UI** | Not implemented | Edit files under `policy-engine/policies/` and `POST /v1/reload` |
| **ASR history across restarts** | In-memory only | Red-team campaigns reset when container restarts |
| **Approval persistence** | In-memory | Agent-gate approvals lost on restart |
| **AuthN / RBAC** | Not implemented | Dashboard is open on the dev port — add auth before production |

## Tests

```bash
cd dashboard && npm run build
```

Backend tests covering new APIs run with `make test-go` and `make test-python`.
