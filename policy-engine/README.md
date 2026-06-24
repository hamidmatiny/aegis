# Policy Engine

Go service for CEL-based policy evaluation over defense verdicts.

## Features (Stage 3)

- **CEL rule evaluation** over `InputVerdict`, `OutputVerdict`, and `ToolCallRequest`
- **Versioned YAML policy packs** with hot-reload (`AEGIS_POLICY_RELOAD_SECONDS`, default 10s)
- **Actions:** `allow`, `block`, `transform`, `escalate_to_judge`
- **Modes:** `enforce`, `shadow`, `dry_run` — shadow/dry-run record `shadow_action` without enforcing
- **Per-tenant overrides** in `policies/tenants/{tenant_id}/`

## API

```bash
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

## CEL context (input)

- `input_verdict.fused_score`
- `input_verdict.action`
- `input_verdict.transformed_content`
- `input_verdict.detector_scores` (list; use `.exists(d, ...)`)
