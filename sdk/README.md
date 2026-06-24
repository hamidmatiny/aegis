# AEGIS SDKs

Drop-in Python and TypeScript clients plus an OpenAI-compatible reverse proxy (Docker `gateway` service on port **8080**).

| Package | Path | Install |
|---------|------|---------|
| Python | [python/](python/) | `pip install -e './sdk/python[dev]'` |
| TypeScript | [typescript/](typescript/) | `cd sdk/typescript && npm install && npm run build` |

## Quick start — reverse-proxy mode (zero code changes)

```bash
docker compose up -d gateway input-defense output-defense policy-engine model-router

export OPENAI_BASE_URL=http://localhost:8080/v1
export OPENAI_API_KEY=dev-local

# Existing OpenAI SDK app — no code changes
python -c "
from openai import OpenAI
c = OpenAI()
print(c.chat.completions.create(model='mock-model', messages=[{'role':'user','content':'Hi'}]))
"
```

Or use the AEGIS SDK directly:

```python
from aegis_sdk import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1")
print(client.chat.completions.create(model="mock-model", messages=[{"role": "user", "content": "Hi"}]))
```

## Embedded mode (SDK orchestrates services)

```python
from aegis_sdk import OpenAI

client = OpenAI()  # uses AEGIS_* env URLs
resp = client.chat.completions.create(
    model="mock-model",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Gateway vs Go orchestrator

Stage 0 scaffolded a **Go gateway** (`gateway/`) as the long-term gRPC/REST orchestration layer. Stage 10 did **not** implement that orchestrator; it wired the Docker **`gateway` service** (port 8080) to the **Python SDK reverse proxy** instead.

**Why port 8080 was given to the SDK proxy (pragmatic, interim):**

- Stage 10’s deliverable was SDK + `OPENAI_BASE_URL` reverse-proxy mode. The pipeline already existed in Python (`DefensePipeline`); exposing it on 8080 made “point your OpenAI client at AEGIS” work immediately without duplicating orchestration in Go.
- The Go gateway was still a health-only stub — no orchestration was removed, only the unused HTTP entry was repurposed.

**Tradeoffs (why this is not the final architecture):**

| Approach | Pros | Cons |
|----------|------|------|
| **What we did** — SDK proxy as `gateway` on 8080 | Fast Stage 10; one URL for apps; no duplicated Go logic yet | Conflates “product gateway” with “SDK dev proxy”; Go `gateway/` orphaned on that port |
| **Separate `sdk-proxy` + Go gateway on 8080** | Clear separation; Go scaffold stays visible | Two HTTP entrypoints; `OPENAI_BASE_URL` less obvious |
| **Finish Go gateway orchestration in Stage 10** | Matches original architecture; better hot-path home | Large scope; duplicates pipeline until shared library exists |

**Intended direction:** Go gateway should eventually own orchestration (gRPC hot path, OTEL, connection pooling). The Python proxy remains valid for SDK development and OpenAI-compat HTTP, but production may colocate orchestration in Go and call the same defense services. Stage 10 optimized for **shipping a verifiable SDK**, not for final gateway placement.

## Streaming

Defended chat (`stream: true` through the SDK proxy or embedded pipeline) is **not supported by design today**, not merely backlog. Output defense must see the full model response before the client should receive it; see [python/README.md — Streaming and output defense](python/README.md#streaming-and-output-defense). Model-router streaming without output/policy gates remains available at `:8082` for non-defended paths.

## Error types

All packages expose:

- `AegisPolicyBlockedError` — defense or policy blocked the request
- `AegisProviderError` — model-router / upstream LLM failure
- `AegisApprovalRequiredError` — agent-gate pending human approval

## E2E

```bash
./scripts/e2e-sdk.sh
```

See package READMEs for full API and environment variable lists.
