# Agent Gate

Go service for deterministic tool/MCP permission enforcement with taint tracking, credential masking, and human approval workflows.

The LLM is never the security boundary — permissions are enforced in code via policy-engine CEL rules plus gate-level sanitization.

## Install and run

### Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build agent-gate policy-engine

curl localhost:8083/health
```

Agent-gate calls policy-engine at `http://policy-engine:8081` inside the compose network.

### Local Go

```bash
cd agent-gate
AEGIS_POLICY_ENGINE_URL=http://localhost:8081 go run ./cmd/agent-gate
```

### Tests without local Go

```bash
docker run --rm -v "$(pwd)/agent-gate:/app" -w /app golang:1.22-alpine go test ./...
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_AGENT_GATE_PORT` | `8083` | HTTP port |
| `AEGIS_POLICY_ENGINE_URL` | `http://localhost:8081` | Policy-engine base URL |
| `AEGIS_APPROVAL_TTL_HOURS` | `24` | Pending approval expiry (in-memory store) |
| `DATABASE_URL` | — | Reserved for Postgres approval persistence (not wired yet) |

## API

```bash
# Health
curl localhost:8083/health
curl localhost:8083/ready

# Evaluate a tool/MCP call (sanitize → policy → decision)
curl -X POST localhost:8083/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "default",
    "mode": "enforce",
    "tool_call": {
      "tool_name": "search_docs",
      "risk_level": "LOW",
      "arguments": [{"name": "query", "value": "deployment guide"}]
    }
  }'

# Irreversible action — returns AWAITING_HUMAN_APPROVAL + approval_request_id
curl -X POST localhost:8083/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "default",
    "tool_call": {
      "tool_name": "delete_database",
      "risk_level": "IRREVERSIBLE",
      "arguments": [{"name": "db_id", "value": "prod-1"}]
    }
  }'

# List pending approvals (dashboard inbox)
curl localhost:8083/v1/approvals

# List all non-expired approvals including decided
curl 'localhost:8083/v1/approvals?status=all'

# Get pending approval
curl localhost:8083/v1/approvals/appr-123456789

# Submit human approval decision
curl -X POST localhost:8083/v1/approvals/appr-123456789/decide \
  -H 'Content-Type: application/json' \
  -d '{
    "approved": true,
    "reviewer_id": "admin@example.com",
    "comment": "Approved for emergency maintenance"
  }'
```

### Response shape (`POST /v1/evaluate`)

```json
{
  "decision": {
    "status": "APPROVED",
    "flagged_taint": [],
    "evaluation_latency_ms": 3
  },
  "sanitized_tool_call": {
    "tool_name": "run_command",
    "arguments": [
      {
        "name": "cmd",
        "value": "curl -H Authorization: Bearer [REDACTED-API_KEY]",
        "contains_credentials": true,
        "masked_value": "..."
      }
    ]
  },
  "policy_action": "allow"
}
```

### Tool call statuses

| Status | Meaning |
|--------|---------|
| `APPROVED` | Policy allowed; execute `sanitized_tool_call` |
| `DENIED` | Policy blocked (e.g. tainted credentials) |
| `AWAITING_HUMAN_APPROVAL` | Irreversible/high-risk; human must approve via `/v1/approvals/{id}/decide` |
| `PENDING` | Reserved for async flows |
| `EXECUTED` | Reserved for post-execution audit (future) |

## Policy integration

Agent-gate calls `POST /v1/evaluate/tool` on policy-engine. Default rules in `policy-engine/policies/default.yaml`:

| Rule | Trigger | Policy action | Gate status |
|------|---------|---------------|-------------|
| `require-approval-irreversible` | `risk_level == 'IRREVERSIBLE'` | `escalate_to_judge` | `AWAITING_HUMAN_APPROVAL` |
| `block-tainted-credentials` | tainted arg with credentials | `block` | `DENIED` |

Risk levels: `LOW`, `MEDIUM`, `HIGH`, `IRREVERSIBLE`.

## End-to-end test

```bash
chmod +x scripts/e2e-agent-gate.sh
docker compose up -d --build agent-gate policy-engine
./scripts/e2e-agent-gate.sh
```

## Tests

```bash
cd agent-gate && go test ./...
make test-go   # from repo root
```

## Known limitations (tracked gaps)

| Component | Status | Follow-up |
|-----------|--------|-----------|
| **Approval store** | In-memory only | Persist to Postgres (`DATABASE_URL` already in compose) |
| **gRPC `AgentGateService`** | Proto defined; HTTP only today | Implement gRPC alongside REST |
| **Audit receipts** | Not emitted yet | Wire to audit service (Stage 8) |
| **Dashboard approval inbox** | `GET /v1/approvals` + dashboard UI | Done (Stage 9) |
| **Tool permission matrix** | Policy CEL only | Per-tool/per-tenant YAML matrix (future) |
| **Credential detection** | Regex patterns | NER / secret scanners for contextual PII |

## Taint tracking

Arguments carry `taint_level` (`TRUSTED`, `UNTRUSTED`, `TAINTED`) and optional `taint_source` (`RAG_DOCUMENT`, `WEB_FETCH`, `TOOL_OUTPUT`, etc.). The gate aggregates taint labels and flags tainted/credential-bearing arguments in the decision.

Credential-bearing arguments are masked before policy evaluation and in `sanitized_tool_call` returned to the caller.
