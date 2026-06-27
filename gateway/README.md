# AEGIS Gateway (Go)

HTTP orchestration layer for the full defense-in-depth pipeline. **Stage H4** implements the originally planned Go gateway on port **8080**, replacing the Python SDK reverse proxy in `docker compose`.

## Pipeline

```
POST /v1/chat/completions
  → input-defense  POST /analyze
  → policy-engine  POST /v1/evaluate/input
  → model-router   POST /v1/chat/completions
  → output-defense POST /analyze
  → policy-engine  POST /v1/evaluate/output
  → OpenAI-shaped response + aegis metadata

POST /v1/tools/evaluate
  → agent-gate POST /v1/evaluate
```

## Install and run

### Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build gateway input-defense output-defense policy-engine model-router agent-gate

curl localhost:8080/health
curl -X POST localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"mock-model","messages":[{"role":"user","content":"Hello"}]}'
```

### Local Go

```bash
cd gateway
AEGIS_INPUT_DEFENSE_URL=http://localhost:8090 \
AEGIS_OUTPUT_DEFENSE_URL=http://localhost:8091 \
AEGIS_POLICY_ENGINE_URL=http://localhost:8081 \
AEGIS_MODEL_ROUTER_URL=http://localhost:8082 \
AEGIS_AGENT_GATE_URL=http://localhost:8083 \
go run ./cmd/gateway
```

### Tests without local Go

```bash
docker run --rm -v "$(pwd)/gateway:/app" -w /app golang:1.22-alpine go test ./...
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_GATEWAY_HTTP_PORT` | `8080` | HTTP listen port |
| `AEGIS_INPUT_DEFENSE_URL` | `http://localhost:8090` | Input defense base URL |
| `AEGIS_OUTPUT_DEFENSE_URL` | `http://localhost:8091` | Output defense base URL |
| `AEGIS_POLICY_ENGINE_URL` | `http://localhost:8081` | Policy engine base URL |
| `AEGIS_MODEL_ROUTER_URL` | `http://localhost:8082` | Model router base URL |
| `AEGIS_AGENT_GATE_URL` | `http://localhost:8083` | Agent gate base URL |
| `AEGIS_DEFAULT_TENANT_ID` | `default` | Tenant id on downstream calls |
| `AEGIS_DEFAULT_MODEL` | `mock-model` | Default model when omitted |
| `AEGIS_GATEWAY_HTTP_TIMEOUT` | `120` | Downstream HTTP timeout (seconds) |

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness (`service: aegis-gateway`, `stage: H4`) |
| GET | `/ready` | Readiness |
| POST | `/v1/chat/completions` | Defended chat (OpenAI-compatible) |
| POST | `/v1/tools/evaluate` | Agent-gate tool evaluation |

### Error responses

| HTTP | `error.type` | When |
|------|--------------|------|
| 403 | `aegis_policy_blocked` | Input/output defense or policy block |
| 403 | `aegis_approval_required` | Agent-gate pending approval |
| 400 | `streaming_unsupported` | `stream: true` (see below) |
| 401/502 | `auth_failed` / provider errors | Model-router upstream failure |

## Streaming decision (H4)

**Defended streaming remains unsupported.** Output defense and output-side policy require the complete assistant response before any content is released. Requests with `"stream": true` receive HTTP **400** with `streaming_unsupported`.

Non-defended streaming is still available directly from model-router (`:8082`) for tooling that bypasses the gateway.

gRPC (`GatewayService` in `shared/proto/aegis/v1/gateway.proto`) is defined but **not yet implemented** — REST is the supported orchestration path in H4.

## Python SDK proxy (embedded mode)

The Python reverse proxy (`aegis-sdk-proxy`, `sdk/python/src/aegis_sdk/proxy/`) remains for SDK development and embedded orchestration:

```bash
pip install -e './sdk/python[dev]'
aegis-sdk-proxy   # optional local dev on 8080 if gateway not running
```

Docker Compose **`gateway`** now builds this Go service. Use the Python proxy only when explicitly running `aegis-sdk-proxy` locally.

## E2E

```bash
chmod +x scripts/e2e-sdk.sh
docker compose up -d --build gateway input-defense output-defense policy-engine model-router
./scripts/e2e-sdk.sh
```

## Known limitations

| Gap | Status |
|-----|--------|
| gRPC `GatewayService` | Proto defined; REST only in H4 |
| OpenTelemetry on hot path | Planned |
| Audit receipt emission from gateway | Downstream services emit; gateway does not yet aggregate |
| Connection pooling / HTTP/2 | Single shared `http.Client` per process |
