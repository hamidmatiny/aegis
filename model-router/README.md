# Model Router

Provider-agnostic LLM routing service with unified streaming interface, configuration-driven provider selection, and fallback/retry logic.

All vendor-specific HTTP logic lives in `internal/provider/` — nothing leaks outside this package.

## Supported providers

| ID | Upstream | Protocol |
|----|----------|----------|
| `openai` | OpenAI API | OpenAI-compatible |
| `anthropic` | Anthropic Messages API | Native |
| `gemini` | Google Generative Language API | Native |
| `ollama` | Local Ollama | OpenAI-compatible (`/v1/chat/completions`) |
| `vllm` | Local vLLM | OpenAI-compatible |
| `mock` | Built-in stub | Dev/test without API keys |

## Configuration

`config/providers.yaml` defines providers, fallback chain, and retry settings. Override path via `AEGIS_MODEL_ROUTER_CONFIG`.

Environment variables:
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
- `OLLAMA_BASE_URL` (overrides ollama base URL)

## API

OpenAI-compatible endpoint for drop-in SDK use:

```bash
# Non-streaming
curl -X POST localhost:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "mock-model",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Streaming (SSE)
curl -N -X POST localhost:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "mock-model",
    "stream": true,
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# List providers
curl localhost:8082/v1/providers
```

Response includes `aegis.fallback_used` and `aegis.attempted_providers` when fallback routing occurs.

## Routing behaviour

1. Resolve primary provider/model from request or config defaults
2. Retry transient upstream errors (`429`, `5xx`) up to `retry.max_attempts`
3. Walk `routing.fallback_chain` on failure
4. Return unified response regardless of upstream vendor
