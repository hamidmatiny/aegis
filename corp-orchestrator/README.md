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
| `AEGIS_AGENT_GATE_REVIEWER_KEYS` | Reviewer key for deferred `POST /v1/tasks/{id}/decide` |
| `AUDIT_SERVICE_URL` | audit base |
| `AEGIS_INTERNAL_TOKEN` | Internal Bearer (also accepted on `/v1/*` for ops) |
| `CORP_FORCE_MOCK_LLM` | Default `true` — scripted tool calls + no API spend; set `false` for real models |
| `CORP_SCHEDULER_ENABLED` | Default `true` — 60s tick, cron from agent `schedule` |
| `CORP_REPO_ROOT` | Repo root for `corp_read_repo_file` / infra checks |
| `CORP_HEALTHZ_URL` | Health URL for web_engineering |
| `CORP_GITHUB_ACTIONS_URL` | Actions API URL |
| `CORP_INPUT_DEFENSE_URL` / `CORP_OUTPUT_DEFENSE_URL` | Red team probe targets |
| `CORP_ORCHESTRATOR_PORT` | Default `8094` |

## Auth

`/v1/*` requires an **admin** SMB session cookie (`aegis_smb_session`), verified by the
shared `aegis_smb_session.require_admin_session` package (same check as smb-copilot).
Ops may also send `Authorization: Bearer $AEGIS_INTERNAL_TOKEN`. Customer sessions are rejected.

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

# Run one default task per agent (12)
curl -s -X POST http://127.0.0.1:8094/v1/tasks/run-all-agents \
  -H "Authorization: Bearer $TOKEN"

# List / decide deferred approvals (after AWAITING_HUMAN_APPROVAL parks a task)
curl -s http://127.0.0.1:8094/v1/tasks/pending -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://127.0.0.1:8094/v1/tasks/<task_id>/decide \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"approved":true,"comment":"ok from owner"}'
```

BEV UI: smb-portal `/admin/company` (AdminGuard) → pending list with **Approve & execute**.

## Deferred approval

Scheduled runs use a short `approval_timeout_seconds=5` so they fail closed. When a tool
is escalated, the task is stored as `status=escalated` with `pending_approval` JSON
(`tool_name`, `arguments`, `approval_request_id`, `risk_level`). The owner can approve
later via BEV or `POST /v1/tasks/{id}/decide`, which calls agent-gate
`POST /v1/approvals/{id}/decide` (or re-issues evaluate if the original id expired),
then executes the tool through harness `_execute_after_gate`.

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
| **executive / ceo** | **`0 7 * * *`** (after finance, before sales) |
| hr / agent_ops | `0 * * * *` |
| engineering / core_infra | `0 * * * *` |
| data / quality | `0 */6 * * *` |
| trust / safety_privacy | `0 */12 * * *` |
| sales / growth | `0 8 * * *` |

CEO `allowed_tools`: `corp_read_company_state`, `corp_reprioritize`, `corp_escalate`,
`corp_list_agents` only — **zero** HIGH/IRREVERSIBLE. `corp_read_company_state` is the
single deliberate cross-department read exception (documented in `default.yaml`).

## IRREVERSIBLE / HIGH demos

```bash
export AEGIS_AGENT_GATE_API_KEYS=... AEGIS_AGENT_GATE_REVIEWER_KEYS=... AEGIS_INTERNAL_TOKEN=...
python corp-orchestrator/scripts/demo_irreversible_gates.py
```

Confirms `AWAITING_HUMAN_APPROVAL` for:
`corp_apply_cve_write`, `corp_publish_outreach`, `corp_propose_cve_write`,
`corp_draft_outreach`, `corp_redteam_run` — then parks a pending apply, waits, approves,
and shows the tool actually executing.

## Real LLM one-shot (budget-sensitive)

Requires a **working** `XAI_API_KEY` in model-router. Keep the scheduler off:

```bash
CORP_FORCE_MOCK_LLM=false CORP_SCHEDULER_ENABLED=false \
  docker compose up -d --force-recreate --no-deps corp-orchestrator
python corp-orchestrator/scripts/verify_real_llm_agents.py
```

## Phase 13 open questions

- **Do not** wire 9Router / OmniRoute / Headroom into this production multi-tenant path without a security review — customer prompts would transit those routers.
- Live log-stream timeline for BEV (websocket/SSE) is sequenced for Phase 13.
