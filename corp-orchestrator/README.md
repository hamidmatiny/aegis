# AEGIS Corp Orchestrator

Multi-department agent corporation registry and governed task runner.

Built on existing AEGIS pieces — **does not reinvent agent execution**:

- Execution engine: `aegis_harness.loop.run_agent()` (library import, not CLI subprocess)
- Least privilege: per-agent `ToolRegistry` from `context_scope.allowed_tools`
- Gate: every `tool.execute()` still goes only through harness `_execute_after_gate` → agent-gate → policy-engine
- Cross-department work: **only** via `corp_escalate` (creates a `tasks` row for another agent)
- Audit: optional signed receipt via audit `POST /v1/receipts`

## Install / run

```bash
# From repo root — generate credentials if needed
cp .env.example .env   # or run ./scripts/generate-credentials.sh

docker compose up -d --build postgres redis policy-engine model-router agent-gate audit \
  corp-orchestrator

curl -s http://127.0.0.1:8094/healthz
```

Local (without Docker image rebuild):

```bash
cd harness && pip install -e .
cd ../corp-orchestrator && pip install -e .
export DATABASE_URL=postgres://aegis:aegis_dev@127.0.0.1:5432/aegis?sslmode=disable
export AEGIS_INTERNAL_TOKEN=...
export AEGIS_AGENT_GATE_API_KEYS=...
export SMB_SESSION_SECRET=...
python -m aegis_corp_orchestrator.main
```

## Environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres |
| `REDIS_URL` | Shared with smb-copilot sessions |
| `SMB_SESSION_SECRET` | Verify admin cookie `aegis_smb_session` |
| `MODEL_ROUTER_URL` | model-router base |
| `AGENT_GATE_URL` | agent-gate base |
| `AEGIS_AGENT_GATE_API_KEYS` | Service key (first entry) for evaluate |
| `AUDIT_SERVICE_URL` | audit base |
| `AEGIS_INTERNAL_TOKEN` | Internal Bearer (also accepted on `/v1/*` for ops) |
| `CORP_FORCE_MOCK_LLM` | Default `true` — scripted tool calls + no API spend; set `false` for real models |
| `CORP_SCHEDULER_ENABLED` | Default `true` — 60s tick, cron from agent `schedule` |
| `CORP_REPO_ROOT` | Repo root for `corp_read_repo_file` / infra checks |
| `CORP_HEALTHZ_URL` | Health URL for web_engineering |
| `CORP_GITHUB_ACTIONS_URL` | Actions API URL |
| `CORP_INPUT_DEFENSE_URL` / `CORP_OUTPUT_DEFENSE_URL` | Red team probe targets |
| `CORP_ORCHESTRATOR_PORT` | Default `8094` |

## HTTP

```bash
# Public
curl -s http://127.0.0.1:8094/healthz

# Admin / ops (cookie or internal token)
TOKEN=$AEGIS_INTERNAL_TOKEN
curl -s http://127.0.0.1:8094/v1/agents -H "Authorization: Bearer $TOKEN"
curl -s http://127.0.0.1:8094/v1/bev/summary -H "Authorization: Bearer $TOKEN"

# Run one department's default task
curl -s -X POST http://127.0.0.1:8094/v1/tasks/run \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"department":"engineering","team":"core_infra"}'

# Run one default task per department
curl -s -X POST http://127.0.0.1:8094/v1/tasks/run-all-departments \
  -H "Authorization: Bearer $TOKEN"
```

BEV UI: smb-portal `/admin/company` (AdminGuard) → `/api/corp/v1/bev/*`.

## Default schedules

| Department / team | Cron |
|-------------------|------|
| website / ui_ux_branding | `0 */6 * * *` |
| website / web_engineering | `0 * * * *` |
| website / management_board | `0 */6 * * *` |
| cybersecurity / threat_intel | `0 */12 * * *` |
| cybersecurity / defensive_eng | `0 */12 * * *` |
| cybersecurity / red_team | `0 0 * * *` |
| finance / pnl_analyst | `0 6 * * *` |
| hr / agent_ops | `0 * * * *` |
| engineering / core_infra | `0 * * * *` |
| data / quality | `0 */6 * * *` |
| trust / safety_privacy | `0 */12 * * *` |
| sales / growth | `0 8 * * *` |

## IRREVERSIBLE demos

```bash
python corp-orchestrator/scripts/demo_irreversible_gates.py
```

Demonstrates agent-gate `escalate_to_judge` for `corp_apply_cve_write` and `corp_publish_outreach`.

## Phase 13 open questions

- **Do not** wire 9Router / OmniRoute / Headroom into this production multi-tenant path without a security review — customer prompts would transit those routers.
- Live log-stream timeline for BEV (websocket/SSE) is sequenced for Phase 13.
