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
| `SMB_EMBEDDING_PROVIDER` | Embeddings provider id (default `mock`; for production use `openai`, `ollama`, or `vllm` — Grok does **not** support embeddings) |
| `SMB_EMBEDDING_MODEL` | Embeddings model id (default `mock-embedding`; recommend `text-embedding-3-small` with `SMB_EMBEDDING_PROVIDER=openai`) |
| `OPENAI_API_KEY` | Required when `SMB_EMBEDDING_PROVIDER=openai` (embeddings are very cheap — typically fractions of a cent per intake row) |
| `SMB_CHAT_PROVIDER` | Chat provider for `/qa/ask` (default `mock`; for production recommend `grok`) |
| `SMB_CHAT_MODEL` | Free-tier chat model (default `mock-model`; recommend `grok-4-fast` with `SMB_CHAT_PROVIDER=grok` — ~$0.20/M input, ~$0.50/M output) |
| `SMB_CHAT_MODEL_WALKTHROUGH` | Paid walkthrough model (defaults to `SMB_CHAT_MODEL` if unset; recommend a stronger model such as `grok-4` for paid tier only) |
| `SMB_QA_MAX_TOKENS_FREE` | Max output tokens for free-tier `/qa/ask` (default `500`) |
| `SMB_QA_MAX_TOKENS_WALKTHROUGH` | Max output tokens for paid walkthrough answers (default `1200`) |
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

- **CVE matching** uses a curated seed table (`cve_reference`), not a live NVD/synced feed — see `deploy/postgres/init/007_smb_cve_reference.sql` and startup migration `010_smb_cve_reference_expand.sql`.
- Tier / walkthrough entitlement is **only** policy-engine CEL overrides — do not
  treat `tenants.tier` as the feature flag.
- Compose mounts `policy-engine/policies` into smb-copilot so register can write
  override files; policy-engine still mounts that tree read-only and hot-reloads.
- Walkthrough responses are still advisory text only (no action-taking).


## Billing / usage (audit-backed)

Tier state for walkthroughs still comes from policy-engine CEL overrides. Usage
counts come from `usage_events`, cross-checked against Ed25519-signed audit
receipts (read-only from smb-copilot — signing stays in the audit service).

```bash
# After a few /qa/ask calls:
curl -s http://127.0.0.1:8093/billing/usage -H "Authorization: Bearer $API_KEY"
curl -s http://127.0.0.1:8093/billing/receipts -H "Authorization: Bearer $API_KEY"
```

`GET /billing/usage` includes a `discrepancies` array for any `usage_events` row
without a matching signed receipt (never silently reconciled). `integrity` is
`ok` or `discrepancies_present`.

| Variable | Purpose |
|----------|---------|
| `AUDIT_SERVICE_URL` | Audit service base URL (`GET /v1/receipts`, `/verify`) |
| `AEGIS_INTERNAL_TOKEN` | Bearer token for audit (and policy-engine) calls |
