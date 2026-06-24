# Policy Engine

Go service for CEL-based policy evaluation over defense verdicts.

## Install and run

### Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build policy-engine

curl localhost:8081/health
```

### Local Go

```bash
cd policy-engine
go run ./cmd/policy-engine
```

### Tests without local Go

```bash
docker run --rm -v "$(pwd)/policy-engine:/app" -w /app golang:1.22-alpine go test ./...
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_POLICY_ENGINE_PORT` | `8081` | HTTP port |
| `AEGIS_POLICY_DIR` | `policies` | YAML policy pack directory |
| `AEGIS_POLICY_RELOAD_SECONDS` | `10` | Auto-reload interval (`0` = disabled) |

In Docker, `AEGIS_POLICY_DIR=/etc/aegis/policies` with the host `policies/` directory mounted read-only.

## Features (Stage 3)

- **CEL rule evaluation** over `InputVerdict`, `OutputVerdict`, and `ToolCallRequest`
- **Versioned YAML policy packs** with hot-reload
- **Actions:** `allow`, `block`, `transform`, `escalate_to_judge`
- **Modes:** `enforce`, `shadow`, `dry_run` — shadow/dry-run record `shadow_action` without enforcing
- **Per-tenant overrides** in `policies/tenants/{tenant_id}/`

## API

```bash
# Health
curl localhost:8081/health
curl localhost:8081/ready

# Evaluate input defense verdict
curl -X POST localhost:8081/v1/evaluate/input \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "default",
    "mode": "enforce",
    "input_verdict": {
      "action": "ESCALATE",
      "fused_score": 0.72,
      "detector_scores": [
        {"detector_id": "heuristic", "score": 0.85, "reasoning": "pattern match", "latency_ms": 1}
      ]
    }
  }'

# Evaluate output defense verdict
curl -X POST localhost:8081/v1/evaluate/output \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "default",
    "mode": "enforce",
    "output_verdict": {
      "action": "BLOCK",
      "fused_score": 0.85,
      "detector_scores": [
        {"detector_id": "pii", "score": 0.90, "reasoning": "API key detected", "latency_ms": 2}
      ]
    }
  }'

# Evaluate tool call request
curl -X POST localhost:8081/v1/evaluate/tool \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "default",
    "tool_call": {
      "tool_name": "send_email",
      "arguments": [{"name": "to", "value": "user@example.com", "taint_level": "TAINTED"}],
      "risk_level": "REVERSIBLE"
    }
  }'

# List loaded policy packs
curl localhost:8081/v1/policy-packs

# Hot-reload policies from disk
curl -X POST localhost:8081/v1/reload
```

## Policy pack layout

```
policies/
  default.yaml
  tenants/
    acme/
      overrides.yaml
```

Tenant overrides can disable base rules and append tenant-specific rules by ID.

## CEL context

### Input evaluation

- `input_verdict.fused_score`
- `input_verdict.action`
- `input_verdict.transformed_content`
- `input_verdict.detector_scores` (list; use `.exists(d, ...)`)

### Output evaluation

- `output_verdict.fused_score`
- `output_verdict.action`
- `output_verdict.redacted_content`
- `output_verdict.detector_scores` (list; use `.exists(d, ...)`)

Default output rules (`policies/default.yaml`):

| Rule | CEL | Action |
|------|-----|--------|
| `block-high-output-score` | `fused_score >= 0.80` | `block` |
| `escalate-ambiguous-output` | `fused_score >= 0.50 && fused_score < 0.80` | `escalate_to_judge` |

## End-to-end with output-defense

```bash
# 1. Analyze model output
VERDICT=$(curl -s -X POST localhost:8091/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content": "Here is the API key: sk-live-abc123xyz789"}')

# 2. Evaluate against policy (or use scripts/e2e-output-defense.sh)
curl -X POST localhost:8081/v1/evaluate/output \
  -H 'Content-Type: application/json' \
  -d "{\"tenant_id\":\"default\",\"mode\":\"enforce\",\"output_verdict\":$(echo "$VERDICT" | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin)["verdict"]))')}"
```

## Tests

```bash
cd policy-engine && go test ./...
# or via Docker (see above)
make test-go   # from repo root
```

## Known limitations

| Gap | Status |
|-----|--------|
| Output/tool HTTP paths | Implemented but no dedicated unit tests yet (input path is tested) |
| Full `OutputVerdict` proto fields in CEL | `judge_votes`, `escalation_reason` not exposed to CEL activation yet |
| gRPC policy service | Proto defined; HTTP only today |
| Gateway orchestration | Caller chains services manually until gateway Stage |
