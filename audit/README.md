# Audit Service

Go service for tamper-evident, Ed25519-signed decision receipts stored in Postgres.

Every defense-layer decision can be recorded as an append-only `AuditReceipt` with a SHA-256 payload hash and Ed25519 signature for compliance and forensics.

## Install and run

### Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build postgres audit

curl localhost:8084/health
```

Postgres schema (`audit_receipts` table) is applied automatically from `deploy/postgres/init/001_schema.sql`.

### Local Go

```bash
cd audit
DATABASE_URL=postgres://aegis:aegis_dev@localhost:5432/aegis?sslmode=disable \
AEGIS_AUDIT_SIGNING_KEY_ID=dev-key-1 \
go run ./cmd/audit
```

If `AEGIS_AUDIT_SIGNING_KEY` is unset, the service generates an ephemeral dev key at startup (not suitable for production).

### Tests without local Go

```bash
docker run --rm -v "$(pwd)/audit:/app" -w /app golang:1.22-alpine go test ./...
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_AUDIT_PORT` | `8084` | HTTP port |
| `DATABASE_URL` | — | Postgres connection (required in production) |
| `AEGIS_AUDIT_SIGNING_KEY` | — | Ed25519 key: PEM `PRIVATE KEY` or base64-encoded 32-byte seed |
| `AEGIS_AUDIT_SIGNING_KEY_ID` | `dev-key-1` | Key identifier stored on each receipt |

Generate a production key:

```bash
openssl genpkey -algorithm Ed25519 -out audit.key
# Or export seed: base64-encoded 32 bytes for AEGIS_AUDIT_SIGNING_KEY
```

## HTTP API (port 8084)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness (stage 8) |
| `GET` | `/ready` | Readiness |
| `POST` | `/v1/receipts` | Write and sign a receipt |
| `GET` | `/v1/receipts` | Query receipts (`tenant_id`, `event_type`, `start_time`, `end_time`, `limit`, `cursor`) |
| `GET` | `/v1/receipts/{id}` | Fetch receipt by ID |
| `GET` | `/v1/receipts/{id}/verify` | Verify signature and payload hash |
| `POST` | `/v1/export` | Export receipts as JSON or NDJSON |

### Write receipt

```bash
curl -X POST localhost:8084/v1/receipts \
  -H 'Content-Type: application/json' \
  -d '{
    "event_type": "INPUT_DEFENSE",
    "tenant_id": "default",
    "trace": {"trace_id": "abc", "request_id": "req-1"},
    "input_verdict": {"action": "BLOCK", "fused_score": 0.91},
    "policy_pack_id": "default",
    "policy_pack_version": "1.0.0"
  }'
```

### Verify receipt

```bash
curl localhost:8084/v1/receipts/{receipt_id}/verify
```

## Event types

| Value | Source layer |
|-------|--------------|
| `INPUT_DEFENSE` | Input defense verdict |
| `POLICY_DECISION` | Policy engine decision |
| `OUTPUT_DEFENSE` | Output defense verdict |
| `TOOL_GATE` | Agent gate tool decision |
| `MODEL_ROUTER` | Model router routing event |
| `REDTEAM` | Red-team campaign/probe event |

## Signing model

1. Canonical JSON body is built from receipt fields (excluding `signature`, `payload_hash`, `signer_key_id`).
2. `payload_hash = SHA-256(canonical_json)`.
3. `signature = Ed25519.Sign(private_key, payload_hash)`.
4. Decision payload stored in Postgres `payload` JSONB; crypto fields in dedicated columns.

Verification recomputes the hash and checks the Ed25519 signature.

## E2E

```bash
docker compose up -d --build postgres audit
chmod +x scripts/e2e-audit.sh
./scripts/e2e-audit.sh
```

## Tests

```bash
cd audit && go test ./...
```

7 unit tests cover signing, tamper detection, write/query/verify/export, and HTTP handlers.

## Known gaps

| Gap | Status | Planned |
|-----|--------|---------|
| **gRPC `AuditService`** | HTTP only | Wire protobuf RPC (Stage 9+) |
| **Cross-service emitters** | Manual POST | Auto-emit from input/output defense, agent-gate, redteam (Stage 9+) |
| **Key rotation / JWKS** | Single static key | Multi-key verify endpoint |
| **Public key export** | Not exposed | `GET /v1/keys/{id}` for offline verification |

## Residual risk

Receipts prove integrity of recorded decisions, not correctness of detector logic. Services must call audit write on every enforced decision for complete coverage.
