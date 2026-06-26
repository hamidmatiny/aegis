# AEGIS

**AI-native defense platform** for LLM applications and agentic systems.

AEGIS sits between your application and any LLM provider, enforcing defense-in-depth against prompt injection, jailbreaks, data exfiltration, tool/MCP abuse, and supply-chain tampering — with full tamper-evident audit trails.

## Architecture

```
Application → [SDK / Reverse Proxy] → Gateway (Go)
                                         ├── Input Defense (Python)
                                         ├── Policy Engine (Go + CEL)
                                         ├── Model Router (Go)
                                         ├── Output Defense (Python)
                                         ├── Agent Gate (Go)
                                         └── Audit (Go + Postgres)
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design.

**Phase 2 evidence:** Adaptive red-team campaigns and detector ablation results are summarized in [RESULTS.md](./RESULTS.md) (Stage H3).

## Monorepo layout

| Path | Language | Purpose | Stage |
|------|----------|---------|-------|
| `shared/` | Protobuf + JSON Schema | Cross-service schemas and codegen | 0 |
| `gateway/` | Go | gRPC + REST orchestration (scaffold) | 0 |
| `input-defense/` | Python | Input-side detectors + fusion | 2 |
| `policy-engine/` | Go | CEL policy evaluation | 3 |
| `model-router/` | Go | Provider-agnostic LLM routing | 4 |
| `output-defense/` | Python | Output-side detectors + LLM judge | 5 |
| `agent-gate/` | Go | Tool/MCP permission + taint tracking | 6 |
| `redteam/` | Python | Continuous adversarial testing | 7 |
| `audit/` | Go | Ed25519-signed audit receipts | 8 |
| `dashboard/` | React + TS | Operations UI | 9 |
| `sdk/` | Python + TS | Drop-in SDK wrappers | 10 |
| `examples/` | Mixed | Reference integrations | 11 |
| `deploy/` | Helm + SQL | Production deployment | 0 |

## Quick start

```bash
# 1. Copy environment template (recommended secrets pattern)
cp .env.example .env
# Edit .env — set API keys, ports, etc.

# 2. Install dev dependencies and generate protobuf code
chmod +x scripts/*.sh
./scripts/dev-setup.sh

# 3. Start the full local stack
docker compose up -d --build

# 4. Run smoke tests
make test-integration
```

Use `docker compose --env-file .env up -d` if your shell does not auto-load `.env`.

## Service endpoints

| Service | Port | Health | Docs |
|---------|------|--------|------|
| Gateway | 8080 | `/health` | scaffold |
| Policy Engine | 8081 | `/health` | [policy-engine/README.md](./policy-engine/README.md) |
| Model Router | 8082 | `/health` | [model-router/README.md](./model-router/README.md) |
| Agent Gate | 8083 | `/health` | [agent-gate/README.md](./agent-gate/README.md) |
| Audit | 8084 | `/health` | [audit/README.md](./audit/README.md) |
| Input Defense | 8090 | `/health` | [input-defense/README.md](./input-defense/README.md) |
| Output Defense | 8091 | `/health` | [output-defense/README.md](./output-defense/README.md) |
| Red Team | 8092 | `/health` | [redteam/README.md](./redteam/README.md) |
| Dashboard | 3000 | `/` (UI) | [dashboard/README.md](./dashboard/README.md) |
| SDK Proxy (gateway) | 8080 | `/v1/chat/completions` | [sdk/README.md](./sdk/README.md) |

## Development

```bash
make proto              # Lint + generate from shared/proto
make lint               # Go + Python linters
make test               # Unit tests (Go + Python)
make test-integration   # Docker smoke tests
make bench              # Benchmark harness placeholder
```

### Running tests without local Go

```bash
docker run --rm -v "$(pwd)/model-router:/app" -w /app golang:1.22-alpine go test ./...
docker run --rm -v "$(pwd)/policy-engine:/app" -w /app golang:1.22-alpine go test ./...
```

### Running Python service tests

```bash
cd input-defense && pip install -e '.[dev]' && pytest
cd output-defense && pip install -e '.[dev]' && pytest
```

## Build order

| Stage | Component | Status |
|-------|-----------|--------|
| 0 | Scaffold, shared schemas, CI, docker-compose | Done |
| 2 | Input defense | Done |
| 3 | Policy engine | Done |
| 4 | Model router | Done |
| 5 | Output defense | Done |
| 6 | Agent gate | Done |
| 7 | Red-team engine | Done |
| 8 | Audit service | Done |
| 9 | Dashboard | Done |
| 10 | SDKs | Done |
| 11 | Example apps | Done |

## Environment variables

See [.env.example](./.env.example) for the full list. Key variables by service:

| Variable | Service | Purpose |
|----------|---------|---------|
| `XAI_API_KEY` | model-router | xAI Grok API key (not `GROK_API_KEY`) |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` | model-router | Cloud LLM providers |
| `AEGIS_MODEL_ROUTER_CONFIG` | model-router | Path to `providers.yaml` |
| `AEGIS_POLICY_DIR` | policy-engine | YAML policy pack directory |
| `AEGIS_INPUT_DEFENSE_PORT` | input-defense | HTTP port (default 8090) |
| `AEGIS_OUTPUT_DEFENSE_PORT` | output-defense | HTTP port (default 8091) |
| `AEGIS_POLICY_ENGINE_URL` | agent-gate | Policy-engine base URL |
| `AEGIS_APPROVAL_TTL_HOURS` | agent-gate | Pending approval TTL |
| `AEGIS_REDTEAM_INPUT_DEFENSE_URL` | redteam | Input defense base URL for campaigns |
| `AEGIS_REDTEAM_OUTPUT_DEFENSE_URL` | redteam | Output defense base URL for campaigns |
| `AEGIS_AUDIT_SIGNING_KEY` | audit | Ed25519 signing key (PEM or base64 seed) |
| `AEGIS_AUDIT_SIGNING_KEY_ID` | audit | Signer key identifier on receipts |
| `AEGIS_INPUT_DEFENSE_URL` | sdk-proxy / gateway | Input defense URL for SDK pipeline |
| `AEGIS_MODEL_ROUTER_URL` | sdk-proxy / gateway | Model router URL for SDK pipeline |
| `OPENAI_BASE_URL` | your app | Set to `http://localhost:8080/v1` for reverse-proxy mode |
| `DATABASE_URL` | redteam, audit | Postgres connection |

## License

Apache 2.0 — see [LICENSE](./LICENSE).
