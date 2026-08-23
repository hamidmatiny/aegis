# AEGIS SMB Copilot

Scaffold for the SMB Copilot Python service (schema + health endpoint). Business logic lands in later phases.

Schema lives in `deploy/postgres/init/002_smb_*.sql`–`006_smb_*.sql` so a fresh Postgres volume applies it automatically via `docker-entrypoint-initdb.d` (same path as `001_schema.sql`).

## Install

```bash
cd smb-copilot
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run (compose)

```bash
docker compose up -d --build postgres redis smb-copilot
curl http://127.0.0.1:8093/healthz
```

## Environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string (pgvector-enabled) |
| `POLICY_ENGINE_URL` | Policy engine base URL |
| `AUDIT_SERVICE_URL` | Audit service base URL |
| `MODEL_ROUTER_URL` | Model router base URL |
| `SMB_COPILOT_HOST` | Bind host (default `0.0.0.0`) |
| `SMB_COPILOT_PORT` | Listen port (default `8093`) |
