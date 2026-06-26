# AEGIS Architecture

## Overview

AEGIS is a provider-agnostic security gateway that protects LLM applications through five defense layers. Every decision fuses multiple independent signals; no single detector is the sole gate.

## Defense layers

```mermaid
flowchart LR
    App[Application] --> GW[Gateway]
    GW --> ID[Input Defense]
    ID --> PE[Policy Engine]
    PE --> MR[Model Router]
    MR --> LLM[LLM Provider]
    LLM --> OD[Output Defense]
    OD --> PE2[Policy Engine]
    PE2 --> GW
    GW --> App

    Agent[Agent Tool Call] --> AG[Agent Gate]
    AG --> PE3[Policy Engine]
    PE3 --> Exec[Tool Execution]

    ID & PE & OD & AG --> Audit[Audit Service]
```

### 1. Input Defense (Python) — Stage 2

Intercepts and analyzes all user and retrieved content before it reaches the model.

| Detector | Signal Type | Purpose |
|----------|-------------|---------|
| Heuristic/regex | Deterministic | Known injection markers, encoding tricks |
| Perplexity | Statistical | Token-level PPL anomaly (DistilGPT2; stub optional) |
| Known-answer probe | Game-theoretic | Secret token reproduction test |
| Transformer classifier | ML | Prompt-injection classifier (DeBERTa default; Llama-Prompt-Guard optional) |
| Spotlighting transform | Structural | Delimit untrusted content |

**Output:** `InputVerdict` with fused score, per-detector breakdown, optional transformed content.

**Port:** 8090 — see [input-defense/README.md](./input-defense/README.md)

### 2. Policy Engine (Go + CEL) — Stage 3

Evaluates versioned YAML policy packs with CEL expressions against defense verdicts.

**Actions:** `allow`, `block`, `transform`, `escalate_to_judge`

**Modes:** enforce, shadow (log-only), dry-run

**Port:** 8081 — see [policy-engine/README.md](./policy-engine/README.md)

### 3. Model Router (Go) — Stage 4

Provider-agnostic LLM routing with fallback, retry, and model-retired error surfacing.

**Port:** 8082 — see [model-router/README.md](./model-router/README.md)

### 4. Output Defense (Python) — Stage 5

Analyzes model responses before they reach the application.

| Detector | Purpose |
|----------|---------|
| Toxicity/safety classifier | Harmful content (Toxic-BERT + lexicon; stub optional) |
| PII/secret detector + redactor | Regex credentials + context-gated spaCy NER |
| Backtranslation consistency | model-router restatement divergence (stub optional) |
| LLM-judge ensemble | 3× model-router judges on ambiguous band (stub optional) |

**Output:** `OutputVerdict` with fused score, per-detector breakdown, optional `redacted_content`, optional `judge_votes`.

**Port:** 8091 — see [output-defense/README.md](./output-defense/README.md)

### 5. Agent Gate (Go) — Stage 6

Deterministic, code-level permission system for tool/MCP calls.

| Capability | Description |
|------------|-------------|
| Policy evaluation | Calls policy-engine `/v1/evaluate/tool` for CEL rules |
| Taint tracking | Propagates `taint_level` / `taint_source` on arguments |
| Credential masking | Regex-based detection + `[REDACTED-*]` in sanitized tool calls |
| Human approval | Irreversible actions → `AWAITING_HUMAN_APPROVAL` + `/v1/approvals/{id}/decide` |

**Port:** 8083 — see [agent-gate/README.md](./agent-gate/README.md)

### 6. Red Team Engine (Python) — Stage 7

Continuous adversarial testing in sandboxed staging.

| Capability | Description |
|------------|-------------|
| Attack corpus | Local YAML fixtures targeting input/output defenses (30 attacks, H3 expanded) |
| Mutation strategies | 8 transforms (paraphrase, roleplay, encoding, multi-turn, etc.) |
| Campaign runner | Probes defenses via HTTP; reports bypass rate by target/category |
| **Adaptive campaigns (H3)** | Multi-round: mutate successful bypass payloads (`POST /v1/campaigns/run-adaptive`) |
| Pattern store | In-memory + optional Postgres `attack_patterns` for bypasses |

**Port:** 8092 — see [redteam/README.md](./redteam/README.md)

### 7. Audit Service (Go) — Stage 8

Tamper-evident, Ed25519-signed decision receipts persisted to Postgres.

| Capability | Description |
|------------|-------------|
| Receipt signing | SHA-256 canonical payload hash + Ed25519 signature |
| Persistence | Append-only `audit_receipts` table |
| Query / export | Filter by tenant, event type, time range; JSON/NDJSON export |
| Verification | `GET /v1/receipts/{id}/verify` recomputes hash and checks signature |

**Port:** 8084 — see [audit/README.md](./audit/README.md)

### 8. Dashboard (React + TS) — Stage 9

Operations UI wired to audit, policy-engine, agent-gate, and red-team APIs.

| View | Description |
|------|-------------|
| Attack feed | Recent blocked/escalated audit receipts |
| ASR trends | Red-team campaign bypass rates (session) |
| Policy editor | YAML + CEL dry-run preview |
| Tool matrix | Agent-gate tool rules from policy pack |
| Approval inbox | Pending irreversible-action approvals |
| Audit log | Search/export signed receipts |

**Port:** 3000 — see [dashboard/README.md](./dashboard/README.md)

### 9. SDK (Python + TypeScript) — Stage 10

Drop-in OpenAI-compatible clients and reverse-proxy entry point (`gateway` service).

| Capability | Description |
|------------|-------------|
| Embedded client | Orchestrates input → policy → model-router → output → policy |
| Reverse proxy | `POST /v1/chat/completions` on port 8080 — set `OPENAI_BASE_URL` |
| Error types | `AegisPolicyBlockedError`, `AegisProviderError`, `AegisApprovalRequiredError` |
| Tool gating | `tools.evaluate()` / `POST /v1/tools/evaluate` via agent-gate |

**Port:** 8080 (SDK proxy) — see [sdk/README.md](./sdk/README.md)

### 10. Example applications — Stage 11

Reference integrations in [examples/](examples/):

| App | Demonstrates |
|-----|--------------|
| [chatbot](examples/chatbot/) | Direct prompt injection vs benign chat via SDK proxy |
| [rag-taint](examples/rag-taint/) | Indirect injection in RAG chunks; tainted tool exfil |
| [tool-agent](examples/tool-agent/) | Human approval for irreversible tools; credential taint deny |

Run `./scripts/e2e-examples.sh` with the stack up.

## Shared schemas

All cross-service communication uses protobuf definitions in `shared/proto/aegis/v1/`:

| Message | Description |
|---------|-------------|
| `Request` | Unified gateway entry point |
| `InputVerdict` | Fused input defense result |
| `PolicyDecision` | CEL policy evaluation result |
| `OutputVerdict` | Fused output defense result |
| `ToolCallRequest` | Agent tool/MCP call |
| `AuditReceipt` | Ed25519-signed decision record |

JSON Schema mirrors live in `shared/jsonschema/v1/` for REST/OpenAPI.

## Current wiring (Stages 0–11)

Services run independently via `docker-compose.yml`. Cross-service orchestration through the gateway is planned for later stages. Today:

- **Input defense → policy engine:** caller invokes `POST /analyze` then `POST /v1/evaluate/input`
- **Output defense → policy engine:** caller invokes `POST /analyze` then `POST /v1/evaluate/output`
- **Agent gate → policy engine:** caller invokes `POST /v1/evaluate` (gate calls policy-engine internally)
- **Red team → defenses:** `POST /v1/campaigns/run` probes input-defense and output-defense
- **Audit:** any layer can `POST /v1/receipts` to persist a signed decision receipt
- **Audit wiring:** input-defense, output-defense, policy-engine, and agent-gate emit receipts automatically when `AEGIS_AUDIT_URL` is set
- **SDK / gateway:** `gateway` container runs the Python SDK proxy (interim HTTP entry on 8080) — see [sdk/README.md](./sdk/README.md#gateway-vs-go-orchestrator). Go `gateway/` orchestration is still planned.
- **Streaming:** model-router supports SSE; the **defended** pipeline does not stream to clients because output defense requires the complete assistant response before release (structural — not a TODO). See [sdk/python/README.md](./sdk/python/README.md#streaming-and-output-defense).

See `scripts/e2e-output-defense.sh`, `scripts/e2e-agent-gate.sh`, `scripts/e2e-redteam.sh`, `scripts/e2e-audit.sh`, `scripts/e2e-audit-pipeline.sh`, `scripts/e2e-sdk.sh`, and `scripts/e2e-examples.sh` for working examples.

## Data stores

| Store | Usage |
|-------|-------|
| Postgres + pgvector | Audit logs (append-only), policy packs, attack pattern embeddings |
| Redis | Rate limiting, short-lived session state |

## Observability

- Structured JSON logging from all services
- OpenTelemetry tracing on the gateway hot path (planned)
- Audit receipts provide compliance-grade decision evidence

## Deployment

- **Local:** `docker-compose.yml` (all services + Postgres + Redis)
- **Production:** Helm chart in `deploy/helm/` (placeholder)

## Security principles

1. **Defense-in-depth:** Fuse heuristic + statistical + ML + policy signals
2. **Deterministic action gating:** Tool permissions enforced in code, not by the model
3. **Taint tracking:** External content never silently becomes instruction
4. **Provider-agnostic:** No vendor logic outside `model-router`
5. **Tamper-evident audit:** Every decision signed with Ed25519
6. **Adaptive defense:** Red-team loop feeds new attacks back into detectors
7. **Loud model errors:** Retired/invalid LLM model IDs surface as explicit errors, not silent fallback

## Residual risk

Each service README documents known limitations and tracked gaps for its detectors. A formal threat model document is planned for a future stage.
