# AEGIS Python SDK

Drop-in OpenAI/Anthropic-style clients and an OpenAI-compatible reverse proxy that runs the full AEGIS defense pipeline.

## Install

```bash
cd sdk/python
pip install -e '.[dev]'
```

## Embedded client (orchestrates services directly)

```python
from aegis_sdk import OpenAI, AegisPolicyBlockedError

client = OpenAI()  # reads AEGIS_* service URLs from environment

try:
    resp = client.chat.completions.create(
        model="mock-model",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(resp["choices"][0]["message"]["content"])
except AegisPolicyBlockedError as exc:
    print("Blocked:", exc.layer, exc.policy_action)
```

## Reverse-proxy mode (zero app code changes)

Start the proxy (Docker compose `gateway` service on port **8080**):

```bash
docker compose up -d gateway input-defense output-defense policy-engine model-router
```

Point your existing OpenAI client at AEGIS:

```bash
export OPENAI_BASE_URL=http://localhost:8080/v1
export OPENAI_API_KEY=dev-local   # ignored by AEGIS proxy unless you add auth
```

Or use the SDK as a thin HTTP client:

```python
from aegis_sdk import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1")
resp = client.chat.completions.create(
    model="mock-model",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Tool gating

```python
from aegis_sdk import OpenAI, AegisApprovalRequiredError

client = OpenAI()
try:
    client.tools.evaluate(
        tool_call={
            "tool_name": "delete_database",
            "risk_level": "IRREVERSIBLE",
            "arguments": [{"name": "target", "value": "prod"}],
        }
    )
except AegisApprovalRequiredError as exc:
    print("Needs approval:", exc.approval_id)
```

## Error types

| Exception | Meaning |
|-----------|---------|
| `AegisPolicyBlockedError` | Input/output defense or policy engine blocked the request |
| `AegisProviderError` | Model-router / upstream LLM failure (includes retired model 422) |
| `AegisApprovalRequiredError` | Agent-gate requires human approval for irreversible tool action |

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_INPUT_DEFENSE_URL` | `http://localhost:8090` | Input defense base URL |
| `AEGIS_OUTPUT_DEFENSE_URL` | `http://localhost:8091` | Output defense base URL |
| `AEGIS_POLICY_ENGINE_URL` | `http://localhost:8081` | Policy engine base URL |
| `AEGIS_MODEL_ROUTER_URL` | `http://localhost:8082` | Model router base URL |
| `AEGIS_AGENT_GATE_URL` | `http://localhost:8083` | Agent gate base URL |
| `AEGIS_SDK_PROXY_HOST` | `0.0.0.0` | Proxy bind host |
| `AEGIS_SDK_PROXY_PORT` | `8080` | Proxy bind port |
| `AEGIS_DEFAULT_TENANT_ID` | `default` | Tenant on defense/policy calls |
| `AEGIS_DEFAULT_MODEL` | `mock-model` | Default model when omitted |

## Proxy HTTP API

```bash
curl localhost:8080/health

curl -X POST localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"mock-model","messages":[{"role":"user","content":"Hello"}]}'

curl -X POST localhost:8080/v1/tools/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"tool_call":{"tool_name":"delete_db","risk_level":"IRREVERSIBLE","arguments":[]}}'
```

Blocked requests return HTTP **403** with `error.type = aegis_policy_blocked`.

## Run proxy locally

```bash
AEGIS_INPUT_DEFENSE_URL=http://localhost:8090 \
AEGIS_OUTPUT_DEFENSE_URL=http://localhost:8091 \
AEGIS_POLICY_ENGINE_URL=http://localhost:8081 \
AEGIS_MODEL_ROUTER_URL=http://localhost:8082 \
aegis-sdk-proxy
```

## Tests

```bash
cd sdk/python && pytest
```

## Streaming and output defense

**This is a structural limitation of the current architecture, not a missing feature flag.**

Model-router (Stage 4) supports SSE streaming. The **defended** pipeline does not, and cannot without a different output-defense model:

1. **Input defense + input policy** run on the user prompt before the LLM call — fine to start a stream afterward.
2. **Output defense + output policy** require the **complete** assistant text (PII, backtranslation, fusion, optional judge). Detectors expect full strings, not token deltas.
3. Forwarding tokens as they arrive means output defense runs **after** the client has seen unvetted content, or the server **buffers** the full reply, defends, then sends — pseudo-streaming with a security gate, not true per-token pre-gate streaming.

Streaming via model-router alone still works. Streaming through the **full** pipeline with output-side enforcement before the client reads content is incompatible with naive token passthrough. Buffer-then-stream or weaker chunk heuristics are possible future modes; neither is implemented.

The SDK returns an error when `stream: true` on the defended path.

## Known limitations

| Gap | Notes |
|-----|-------|
| Streaming | **Structural limitation** — see [Streaming and output defense](#streaming-and-output-defense) |
| Anthropic proxy route | Use embedded `Anthropic` client or OpenAI proxy |
| Gateway gRPC | Go gateway scaffold remains; HTTP entry is SDK proxy |
