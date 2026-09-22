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

If `AEGIS_AUDIT_SIGNING_KEY` is unset when running locally, the service generates an **ephemeral** dev key at each startup. Receipts signed before a restart will fail verification with `unknown signing key id "..."` even when untouched — the payload hash still matches, but a fresh ephemeral key has no way to know about the ID a previous ephemeral run signed under, since it isn't in `AEGIS_AUDIT_SIGNING_KEYS_HISTORY` (there's nothing to put there for a key nobody saved).

Docker Compose sets a **stable dev-only seed** by default so receipts survive container restarts. Override `AEGIS_AUDIT_SIGNING_KEY` in production with a real secret (PEM or base64 32-byte seed).

Rotating a real (non-ephemeral) key no longer breaks verification of old receipts: `scripts/generate-credentials.sh --rotate` snapshots the outgoing key's public half into `AEGIS_AUDIT_SIGNING_KEYS_HISTORY` before generating a new key, and `Signer.VerifyReceipt` checks a receipt's `signer_key_id` against either the current key or that history. A receipt whose key id is genuinely unknown (never the current key, never in history) fails closed with the same `unknown signing key id` message — this is also what happens if `AEGIS_AUDIT_SIGNING_KEYS_HISTORY` is misconfigured or lost.

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
| `AEGIS_AUDIT_SIGNING_KEYS_HISTORY` | — | Retired keys' public halves: `keyID:base64PublicKey`, comma-separated. Maintained automatically by `scripts/generate-credentials.sh` on rotation. **v1 publication source** — independently publishable, not durable across rebuild/config loss |
| `AEGIS_AUDIT_PUBLIC_KEYS` | off | When `true`/`1`/`yes`, `GET /v1/keys`, `GET /v1/keys/{id}`, and `GET /.well-known/jwks.json` are unauthenticated (opt-in external offline verify). Off by default |
| `AEGIS_AUDIT_KEYS_URI` | — | Optional absolute JWKS URL advertised on export as `X-Aegis-Keys-Uri` (export metadata only — not inside signed receipts) |
| `AEGIS_INTERNAL_TOKEN` | — | Required shared service token (all routes except `/health`, `/ready`, and opt-in public key paths) |

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
| `POST` | `/v1/export` | Export receipts as JSON or NDJSON; may set `X-Aegis-Keys-Uri` when configured |
| `GET` | `/v1/keys` | JWKS of current + historical public keys (`aegis_status`: `active` \| `retired`) |
| `GET` | `/v1/keys/{id}` | Single JWK by `signer_key_id`; 404 if unknown |
| `GET` | `/.well-known/jwks.json` | Same body as `GET /v1/keys` |

Public key routes require `AEGIS_AUDIT_PUBLIC_KEYS=true` (or an internal token). JWKS is **key discovery**, not a trust anchor — see [docs/design/audit-jwks-key-export.md](../docs/design/audit-jwks-key-export.md).

### Fetch published keys (offline verify material)

```bash
# Opt in on the server: AEGIS_AUDIT_PUBLIC_KEYS=true
curl -s localhost:8084/v1/keys | jq .
curl -s localhost:8084/v1/keys/dev-key-1 | jq .
```

Offline path: establish trust in the publisher (TLS / out-of-band) → fetch JWKS once → **pin** the JWK(s) with the evidence package → verify receipts later with `signer_key_id` → `x` (no live AEGIS). `retired` means not used for new signing; historical signatures remain valid. Compromise is a separate optional `aegis_compromised_at` field (not implied by retirement).

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

7 unit tests cover signing, tamper detection, write/query/verify/export, HTTP handlers, and JWKS / key publication.

## Known gaps

| Gap | Status | Planned |
|-----|--------|---------|
| **gRPC `AuditService`** | HTTP only | Wire protobuf RPC (Stage 9+) |
| **Cross-service emitters** | Manual POST | Auto-emit from input/output defense, agent-gate, redteam (Stage 9+) |
| **Key rotation / JWKS** | **v1 shipped** (env-backed publication; not durable) | **v1.1:** Postgres append-only key history. Design: [audit-jwks-key-export.md](../docs/design/audit-jwks-key-export.md) (#63, refined after external review) |
| **Public key export** | **v1 shipped** (`GET /v1/keys/{id}`, opt-in public read) | Same design; pin keys with evidence for long-lived offline verify |

## Residual risk

Receipts prove integrity of recorded decisions, not correctness of detector logic. Services must call audit write on every enforced decision for complete coverage.
