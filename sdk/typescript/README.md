# AEGIS TypeScript SDK

OpenAI-compatible client with embedded defense pipeline orchestration or reverse-proxy mode.

## Install

```bash
cd sdk/typescript
npm install
npm run build
```

## Usage

```typescript
import { OpenAI, AegisPolicyBlockedError } from "@aegis/sdk";

const client = new OpenAI();

try {
  const resp = await client.chat.completions.create({
    model: "mock-model",
    messages: [{ role: "user", content: "Hello" }],
  });
  console.log(resp);
} catch (err) {
  if (err instanceof AegisPolicyBlockedError) {
    console.error("Blocked at", err.layer);
  }
}
```

## Reverse-proxy mode

```typescript
const client = new OpenAI({ baseUrl: "http://localhost:8080/v1" });
```

Or set `OPENAI_BASE_URL=http://localhost:8080/v1` in apps using the official OpenAI SDK.

## Environment variables

Same as Python SDK — `AEGIS_INPUT_DEFENSE_URL`, `AEGIS_OUTPUT_DEFENSE_URL`, `AEGIS_POLICY_ENGINE_URL`, `AEGIS_MODEL_ROUTER_URL`, `AEGIS_AGENT_GATE_URL`, `AEGIS_DEFAULT_MODEL`.

## Tests

```bash
npm run build && npm test
```

## Known limitations

| Gap | Notes |
|-----|-------|
| Streaming (defended path) | **Structural** — output defense needs full assistant text; [details](python/README.md#streaming-and-output-defense) |
| Anthropic wrapper | Use OpenAI client or official SDK + proxy |
