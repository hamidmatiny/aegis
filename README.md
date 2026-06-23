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

## Monorepo Layout

| Path | Language | Purpose |
|------|----------|---------|
| `shared/` | Protobuf + JSON Schema | Cross-service schemas and codegen |
| `gateway/` | Go | gRPC + REST orchestration |
| `input-defense/` | Python | Input-side detectors |
| `policy-engine/` | Go | CEL policy evaluation |
| `model-router/` | Go | Provider-agnostic LLM routing |
| `output-defense/` | Python | Output-side detectors + LLM judge |
| `agent-gate/` | Go | Tool/MCP permission + taint tracking |
| `redteam/` | Python | Continuous adversarial testing |
| `audit/` | Go | Ed25519-signed audit receipts |
| `dashboard/` | React + TS | Operations UI |
| `sdk/` | Python + TS | Drop-in SDK wrappers |
| `examples/` | Mixed | Reference integrations |
| `deploy/` | Helm + SQL | Production deployment |

## Quick Start (Stage 0)

```bash
# Copy environment template
cp .env.example .env

# Install dev dependencies and generate protobuf code
chmod +x scripts/*.sh
./scripts/dev-setup.sh

# Start the full local stack
make docker-up

# Run smoke tests
make test-integration
```

Health endpoints:

| Service | URL |
|---------|-----|
| Gateway | http://localhost:8080/health |
| Policy Engine | http://localhost:8081/health |
| Model Router | http://localhost:8082/health |
| Agent Gate | http://localhost:8083/health |
| Audit | http://localhost:8084/health |
| Input Defense | http://localhost:8090/health |
| Output Defense | http://localhost:8091/health |
| Red Team | http://localhost:8092/health |

## Development

```bash
make proto          # Lint + generate from shared/proto
make lint           # Go + Python + TS linters
make test           # Unit tests
make test-integration  # Docker smoke tests
make bench          # Benchmark harness (ASR + latency)
```

## Build Order

1. **Stage 0** (current): Scaffold, shared schemas, CI, docker-compose
2. **Stage 2**: Input defense detectors
3. **Stage 3**: Policy engine
4. **Stage 4**: Model router
5. **Stage 5**: Output defense
6. **Stage 6**: Agent gate
7. **Stage 7**: Red-team engine
8. **Stage 8**: Audit service
9. **Stage 9**: Dashboard
10. **Stage 10**: SDKs
11. **Stage 11**: Example apps

## License

Apache 2.0 — see [LICENSE](./LICENSE).
