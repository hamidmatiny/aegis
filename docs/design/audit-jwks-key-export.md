# Design: Offline trust for exported audit receipts (JWKS & key export)

**Status:** draft design (not implemented)  
**Issue:** [#63](https://github.com/hamidmatiny/aegis/issues/63) — interop / offline trust for exported receipts  
**Owner proposal:** `aegis-audit` (Phase 1 component owner), 2026-09-20  
**Related gaps:** `audit/README.md` → Known gaps → “Key rotation / JWKS”, “Public key export”

---

## 1. Problem / current state

AEGIS audit already has a strong *receipt integrity* primitive:

- append-only `AuditReceipt` records
- SHA-256 payload binding
- Ed25519 signatures with `signer_key_id`
- in-process historical verify via `AEGIS_AUDIT_SIGNING_KEYS_HISTORY`
- `POST /v1/verify` and `POST /v1/export` (JSON / NDJSON)

What it does **not** have (explicitly listed as planned, not built):

| Gap (README) | Today |
|--------------|--------|
| Public key export | Not exposed — no `GET /v1/keys/{id}` |
| Key rotation / JWKS | History exists only as **service env config**; no published multi-key discovery surface |

So for a third party who receives an export months later:

- **Receipt integrity** is offline-checkable *if* they already have the matching public key(s).
- **Trust in the signer** still terminates at (or requires out-of-band coordination with) the originating deployment — closest to option **4** in #63, even though the format was designed for historical-key verify (which only pays off toward options **1** or **3**).

Hamid’s reply on #63 agrees: durable trust anchors are not designed yet; lean toward **independent publication** of key history rather than bundling only at export time; single receipts are the unit today (no collection binding); decision→execution correlation is a separate named gap.

---

## 2. Goals

1. Publish a **durable, independently fetchable** trust anchor for every historical `signer_key_id` that may appear on exported receipts — not only live env vars on the verifier host.
2. Ship the two README-planned surfaces: `GET /v1/keys/{id}` and a JWKS (multi-key) publication endpoint.
3. Document a clear offline verify path: fetch keys once → verify receipts forever without calling AEGIS again (assuming keys were published while still available).
4. Name (but not necessarily implement in v1) collection-level binding and decision→execution binding so BoundaryAttest-class consumers don’t assume coverage that doesn’t exist.

## 3. Non-goals (v1)

- Re-signing, wrapping, or replacing the native `AuditReceipt` format.
- A transparency log / blockchain for keys (optional later; not required to close the README gaps).
- Binding downstream tool *execution results* into the receipt (separate workstream).
- Changing `/v1/export` default to always embed full key material (see §5 — prefer independent publication).

---

## 4. Proposed API

### 4.1 `GET /v1/keys/{id}`

Return one public key by `signer_key_id` (`kid`).

**200 response (JWK, RFC 7517 OKP / Ed25519):**

```json
{
  "kty": "OKP",
  "crv": "Ed25519",
  "kid": "aegis-audit-2026-09",
  "x": "<base64url 32-byte public key>",
  "use": "sig",
  "alg": "EdDSA"
}
```

**Optional AEGIS extensions** (queryable metadata; not required for Ed25519 verify):

```json
{
  "aegis_status": "active" | "retired",
  "aegis_not_before": "2026-01-01T00:00:00Z",
  "aegis_retired_at": "2026-09-01T00:00:00Z"
}
```

**404** if `id` is unknown (fail closed — same spirit as `unknown signing key id` on verify).

**Auth:** public read for self-hosted / operator deployments that intend third-party offline verify. Operators who do *not* want public key discovery keep audit behind their existing network boundary (same as today for `/v1/export`). Document that publishing keys is an explicit ops choice.

### 4.2 `GET /v1/keys` (JWKS document)

RFC 7517 JWKS listing **current + all historical** public keys known to this deployment.

```json
{
  "keys": [ /* JWK objects as above */ ]
}
```

Also expose discovery alias (optional, same body):

- `GET /.well-known/jwks.json` → same JWKS (common verifier expectation)

**Caching:** `Cache-Control: public, max-age=300` (or similar) + `ETag`. Keys only grow / change on rotation; short TTL is fine.

**`kid` mapping:** exactly `AuditReceipt.signer_key_id`. No silent remapping.

### 4.3 Implementation source of truth (v1)

v1 **serves** what the process already trusts for verify:

- current key from `AEGIS_AUDIT_SIGNING_KEY` (+ its id)
- retired public halves from `AEGIS_AUDIT_SIGNING_KEYS_HISTORY`

That closes the “not exposed” gap without inventing a new store on day one.

**v1.1 (recommended follow-on):** persist key history in Postgres (append-only `audit_signing_keys` table) so publication survives env loss / rebuilds. Env history remains a bootstrap / import path. This is the real answer to “durable” vs “whatever was in the container env when someone last rotated.”

---

## 5. Rotation / validity: export inline vs publish separately

**Decision (aligned with Hamid’s lean on #63): independent publication is authoritative.**

| Channel | Role |
|---------|------|
| `GET /v1/keys` / `GET /v1/keys/{id}` | **Source of truth** for third-party trust anchors and rotation/validity metadata |
| Optional hint on export | Convenience only — e.g. `keys_uri` pointing at the JWKS URL of the exporting deployment; **not** a substitute for fetching/publishing keys |
| Bundling full JWKS inside every export | **Not** default — freezes a snapshot that can go stale relative to later retirements; encourages “trust the bag” over “trust the published history” |

Rotation state (`active` / `retired`, timestamps) should live on the **published** key objects (extensions above), not only inside a one-shot export package.

Operators who air-gap verifiers may still **mirror** JWKS out-of-band (copy the JSON once). That is still “independently published,” just not live-fetched.

---

## 6. Portable unit: single receipt vs manifest / checkpoint

**Today:** one signed receipt is the portable unit. `/v1/export` is a bag of receipts with no collection-level signature.

**Proposal — phased:**

| Phase | What |
|-------|------|
| **v1** | Keep single-receipt as the cryptographic unit; document that an NDJSON/JSON export is an unordered bag unless the consumer adds their own packaging |
| **v1.1 (optional)** | `AuditExportManifest`: `{ export_id, created_at, receipt_ids[], receipts_root, signer_key_id, signature }` where `receipts_root` is a Merkle root (or sorted SHA-256 concatenation) over receipt payload hashes. Signed with the **current** audit key. Export may include `manifest` alongside receipts |

Manifest answers #63’s “is one receipt the right unit, or should a set bind?” — **both**: receipt remains atomic; manifest is optional collection binding for auditors who need set integrity.

---

## 7. Decision vs execution binding (named gap)

Receipts today bind the **policy / tool-gate decision** (allow / deny / escalate and related decision payload), **not** necessarily the downstream executed action/result.

That is a real interoperability gap for “what happened after the gate.” **Out of scope for JWKS v1**, but should stay named in docs so consumers (BoundaryAttest, compliance packs) do not assume decision→execution correlation. Candidate follow-on: optional `execution_ref` / result hash field on a future receipt schema version — separate design.

---

## 8. Trust model for third parties

**Target offline path (options 1 / 3 in #63):**

1. Obtain JWKS (or specific `kid` via `GET /v1/keys/{id}`) from the publishing deployment or an out-of-band mirror while keys are still published.
2. Pin / store those public keys with the evidence package if desired.
3. Later: verify each receipt’s signature offline using `signer_key_id` → JWK `x`; no live AEGIS required.

**What still requires operator honesty:** that the JWKS publisher is the same authority that signed the receipts (deployment identity / TLS / out-of-band key ceremony). JWKS does not invent a global PKI; it removes the “you had to be on the box to read the env” barrier.

---

## 9. Migration / rollout

1. Add handlers in `audit/internal/api` for `GET /v1/keys` and `GET /v1/keys/{id}` (and optional `/.well-known/jwks.json`).
2. Build JWKS from current signer + `ParseHistoricalKeys` (existing code path).
3. Unit tests: known kid → 200; unknown → 404; JWKS contains current + history; rotation fixture matches `TestVerifySucceedsAfterRotationWithHistory`.
4. Update `audit/README.md` Known gaps rows to “shipped (v1)” / “Postgres durability (v1.1)”.
5. Optional: add `keys_uri` field on export response metadata (non-breaking).
6. Open follow-up issues: Postgres key history table; optional `AuditExportManifest`; decision→execution binding design.

---

## 10. Open questions for Hamid

1. Should key endpoints be **unauthenticated by default** on self-hosted audit, or gated behind the same internal auth as write/verify?
2. Is Postgres-backed key history (**v1.1**) required before calling the README gaps “closed,” or is env-sourced JWKS enough for a first merge?
3. Priority of **export manifest** vs key export alone for BoundaryAttest-style consumers?
4. Should receipts grow an optional `jwks_uri` / `keys_uri` hint in a schema bump, or keep discovery solely out-of-band / export metadata?

---

## 11. Acceptance criteria (when we implement)

- [ ] `GET /v1/keys/{id}` returns JWK for current and historical ids used in fixtures
- [ ] `GET /v1/keys` (JWKS) lists the same set; unknown id → 404
- [ ] Documented offline verify recipe using only exported receipts + fetched JWKS
- [ ] README Known gaps updated; #63 linked from the design
- [ ] Explicit doc note: decision≠execution; export bag≠manifest until v1.1
