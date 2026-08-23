# AEGIS SMB Copilot

Python service for SMB tenant onboarding, infra-memory Q&A, and paid-tier
walkthrough gating via policy-engine CEL overrides.

Schema lives in `deploy/postgres/init/002_smb_*.sql`–`007_smb_*.sql` so a fresh
Postgres volume applies it automatically via `docker-entrypoint-initdb.d`.

## Install

```bash
cd smb-copilot
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run (compose)

```bash
cp .env.example .env   # if needed
docker compose up -d --build postgres redis policy-engine model-router smb-copilot
curl http://127.0.0.1:8093/healthz
```

## Environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string (pgvector-enabled) |
| `POLICY_ENGINE_URL` | Policy engine base URL (`POST /v1/evaluate/tool`) |
| `AEGIS_POLICY_TENANTS_DIR` | Writable `policies/tenants` path for free-tier `overrides.yaml` |
| `AUDIT_SERVICE_URL` | Audit service base URL |
| `MODEL_ROUTER_URL` | Model router base URL (embeddings + chat) |
| `AEGIS_INTERNAL_TOKEN` | Shared internal token for model-router calls |
| `SMB_EMBEDDING_PROVIDER` | Embeddings provider id (default `mock`) |
| `SMB_EMBEDDING_MODEL` | Embeddings model id (default `mock-embedding`) |
| `SMB_CHAT_PROVIDER` | Chat provider for `/qa/ask` (default `mock`) |
| `SMB_CHAT_MODEL` | Chat model id (default `mock-model`) |
| `SMB_QA_RATE_LIMIT` | Max `/qa/ask` calls per tenant per window (default `5`) |
| `SMB_QA_RATE_WINDOW_SEC` | Rate-limit window seconds (default `60`) |
| `REDIS_URL` | Redis URL for per-tenant Q&A rate limiting |
| `SMB_COPILOT_HOST` | Bind host (default `0.0.0.0`) |
| `SMB_COPILOT_PORT` | Listen port (default `8093`) |

## Endpoints

```bash
# Register (writes policy-engine/policies/tenants/<slug>/overrides.yaml — free tier)
curl -s -X POST http://127.0.0.1:8093/onboarding/register \
  -H 'Content-Type: application/json' \
  -d '{"slug":"acme-smb","tier":"standard"}'

# Plain advisory Q&A (free)
curl -s -X POST http://127.0.0.1:8093/qa/ask \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"question":"How do I harden postgres?"}'

# Guided walkthrough (paid — gated by policy-engine CEL)
curl -s -X POST http://127.0.0.1:8093/qa/ask \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Walk me through hardening postgres","walkthrough":true}'
```

Free tenants receive a structured **upsell** JSON (`type: upsell`), not a bare 403.
Paid tenants: set `smb-deny-walkthrough` to `enabled: false` in that tenant's
`overrides.yaml`, then `curl -X POST http://127.0.0.1:8081/v1/reload`.

## Tests

```bash
cd smb-copilot && source .venv/bin/activate
pytest tests/test_billing.py tests/test_qa.py tests/test_onboarding.py -v
```

## Known limitations

- Tier / walkthrough entitlement is **only** policy-engine CEL overrides — do not
  treat `tenants.tier` as the feature flag.
- Compose mounts `policy-engine/policies` into smb-copilot so register can write
  override files; policy-engine still mounts that tree read-only and hot-reloads.
- Walkthrough responses are still advisory text only (no action-taking).
