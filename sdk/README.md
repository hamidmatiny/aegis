# AEGIS SDKs

Drop-in Python and TypeScript clients plus a **Go gateway** on port **8080** (Docker `gateway` service).

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

## Gateway (Go orchestrator)

**Stage H4 (done):** Docker `gateway` on port **8080** is the **Go orchestrator** (`gateway/`). It runs the same pipeline as the Python SDK (`input → policy → model-router → output → policy`).

Use `OPENAI_BASE_URL=http://localhost:8080/v1` for reverse-proxy mode — no application code changes.

The Python **SDK proxy** (`aegis-sdk-proxy`) remains for embedded/local development when you run it explicitly; it is no longer the compose `gateway` service.

| Component | Role |
|-----------|------|
| **Go gateway** (`gateway/`, compose `gateway:8080`) | Production HTTP entrypoint; defended chat + tool evaluate |
| **Python SDK proxy** (`aegis-sdk-proxy`) | Optional dev/embedded orchestration |
| **Python `DefensePipeline`** | In-process orchestration via `OpenAI()` client without HTTP gateway |

gRPC orchestration (`shared/proto/aegis/v1/gateway.proto`) is defined; REST is implemented in H4.

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
