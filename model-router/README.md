# Model Router

Provider-agnostic LLM routing service with unified streaming interface, configuration-driven provider selection, and fallback/retry logic.

All vendor-specific HTTP logic lives in `internal/provider/` — nothing leaks outside this package.

## Install and run

### Docker (recommended)

```bash
cp .env.example .env
# Set XAI_API_KEY, OPENAI_API_KEY, etc. in .env
docker compose up -d --build model-router

curl localhost:8082/health
curl localhost:8082/v1/providers
```

Use `docker compose --env-file .env up -d model-router` — do not rely on manual `export` + `docker run -e VARNAME`.

### Local Go

```bash
cd model-router
AEGIS_MODEL_ROUTER_CONFIG=config/providers.yaml go run ./cmd/model-router
```

### Tests without local Go

```bash
docker run --rm -v "$(pwd)/model-router:/app" -w /app golang:1.22-alpine go test ./...
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_MODEL_ROUTER_PORT` | `8082` | HTTP port |
| `AEGIS_MODEL_ROUTER_CONFIG` | `config/providers.yaml` | Provider config path |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GOOGLE_API_KEY` | — | Google Gemini API key |
| `XAI_API_KEY` | — | **xAI Grok API key** (use this name, not `GROK_API_KEY`) |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434/v1` | Override Ollama base URL |

## Supported providers

| ID | Upstream | Protocol |
|----|----------|----------|
| `openai` | OpenAI API | OpenAI-compatible |
| `anthropic` | Anthropic Messages API | Native |
| `gemini` | Google Generative Language API | Native |
| `ollama` | Local Ollama | OpenAI-compatible (`/v1/chat/completions`) |
| `vllm` | Local vLLM | OpenAI-compatible |
| `grok` | xAI Grok API | OpenAI-compatible (`https://api.x.ai/v1`) — default model `grok-4.3` |
| `mock` | Built-in stub | Dev/test without API keys |

Alternative Grok model for build/tooling workloads: **`grok-build-0.1`** — set in `providers.yaml` or pass in the request `model` field.

## Configuration

`config/providers.yaml` defines providers, fallback chain, and retry settings. Override path via `AEGIS_MODEL_ROUTER_CONFIG`.

## API

```bash
# Health
curl localhost:8082/health
curl localhost:8082/ready

# Non-streaming chat (defaults to mock provider)
curl -X POST localhost:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "mock-model",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Grok with explicit provider
curl -X POST localhost:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "provider": "grok",
    "model": "grok-4.3",
    "messages": [{"role": "user", "content": "Say hello in one word."}]
  }'

# Streaming (SSE)
curl -N -X POST localhost:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "mock-model",
    "stream": true,
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# List providers (includes model_status probe)
curl localhost:8082/v1/providers
```

Response includes `aegis.fallback_used` and `aegis.attempted_providers` when fallback routing occurs.

### Model retired errors (HTTP 422)

When a configured model ID is rejected by the upstream (retired, renamed, or typo), the router **does not** silently fall back. It returns HTTP **422** with `aegis.model_error`:

```json
{
  "error": "provider \"grok\" rejected model \"grok-2-latest\": ...",
  "aegis": {
    "model_error": {
      "provider": "grok",
      "rejected_model": "grok-2-latest",
      "error_type": "model_retired",
      "message": "Model \"grok-2-latest\" on provider \"grok\" was rejected as not found. ..."
    }
  }
}
```

Fix by updating `model-router/config/providers.yaml` with a current model ID.

### Provider health (`GET /v1/providers`)

| `healthy` | `model_status` | Meaning |
|-----------|----------------|---------|
| `true` | `"ok"` | Reachable and default model accepted |
| `true` | `"invalid_model"` | Reachable but configured default model rejected — see `model_error` |
| `false` | `"unreachable"` | Network/auth/upstream down |
| `false` | `"not_checked"` | Provider disabled or no default model configured |

Note: this endpoint performs live upstream Ping + minimal completion probes when API keys are set (may incur latency/cost).

## Routing behaviour

1. Resolve primary provider/model from request or config defaults
2. Retry transient upstream errors (`429`, `5xx`) up to `retry.max_attempts`
3. **Stop immediately** on model-not-found / retired errors — no retry, no fallback
4. Walk `routing.fallback_chain` on other failures
5. Return unified response regardless of upstream vendor

## Tests

```bash
cd model-router && go test ./...
# or Docker (see above)
make test-go   # from repo root
```

## Known limitations

| Gap | Status |
|-----|--------|
| `grok-build-0.1` | Documented but not preconfigured in fallback chain |
| Provider env override | Only `OLLAMA_BASE_URL` overridable via env; other base URLs are yaml-only |
| `/v1/providers` unit tests | Limited coverage of `model_status` fields |
| Gateway integration | Model router called directly; gateway orchestration is future work |
