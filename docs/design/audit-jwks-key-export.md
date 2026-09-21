# Design: Offline trust for exported audit receipts (JWKS & key export)

**Status:** design refined after external review on [#63](https://github.com/hamidmatiny/aegis/issues/63) (2026-09-20); **v1 implementation** ships key publication in the accompanying PR  
**Issue:** [#63](https://github.com/hamidmatiny/aegis/issues/63) — interop / offline trust for exported receipts  
**Merged design PR:** [#70](https://github.com/hamidmatiny/aegis/pull/70)  
**Design refinement PR:** follow-on docs PR folding the #63 review  
**Owner proposal:** `aegis-audit` (Phase 1 component owner), refined with BoundaryAttest / Cullen Meyers review  
**Related gaps:** `audit/README.md` → Known gaps → “Key rotation / JWKS”, “Public key export”

---

## 1. Problem / current state

AEGIS audit already has a strong *receipt integrity* primitive:

- append-only `AuditReceipt` records
- SHA-256 payload binding
- Ed25519 signatures with `signer_key_id`
- in-process historical verify via `AEGIS_AUDIT_SIGNING_KEYS_HISTORY`
- `GET …/verify` and `POST /v1/export` (JSON / NDJSON)

What it does **not** have (explicitly listed as planned, not built):

| Gap (README) | Today |
|--------------|--------|
| Public key export | Not exposed — no `GET /v1/keys/{id}` |
| Key rotation / JWKS | History exists only as **service env config**; no published multi-key discovery surface |

So for a third party who receives an export months later:

- **Receipt integrity** is offline-checkable *if* they already have the matching public key(s).
- **Trust in the signer** still terminates at (or requires out-of-band coordination with) the originating deployment.

---

## 2. Three distinct concepts (do not conflate)

External review on #63 made this separation mandatory before implementation:

| Concept | What it is | What it is **not** |
|---------|------------|-------------------|
| **Key discovery / publication** | JWKS / `GET /v1/keys/{id}` — how a verifier **retrieves** historical public key material | Establishing that the publisher is the real AEGIS signer |
| **Trust anchor** | The verifier’s **independently established** trust in the publisher (TLS / deployment identity / out-of-band ceremony — §8) | Merely the presence of a key in a JWKS document |
| **Verification material** | The concrete public key bytes (JWK `x`) used for Ed25519 verify — often **pinned** with the evidence package for long-lived evidence | A live URL that must be re-fetched forever |

**JWKS alone never establishes signer trust.** Putting a key in JWKS only solves retrieval. Trust that “this JWKS belongs to the deployment that signed these receipts” comes from the out-of-band / TLS / deployment-identity path in §8.

**Recommendation for long-lived evidence:** fetch once through the verifier’s trusted channel, then **pin/store the exact key material with the evidence package**. Later offline verify uses the pin, not a live call.

---

## 3. Goals

1. Publish **independently fetchable** historical verification material for every `signer_key_id` that may appear on exported receipts (v1: env-backed; v1.1: durable Postgres — see §5).
2. Ship `GET /v1/keys/{id}` and JWKS (`GET /v1/keys`, optional `/.well-known/jwks.json`).
3. Document offline verify: discover → pin → verify forever without calling AEGIS again.
4. Keep native `AuditReceipt` authoritative — no second receipt format.
5. Name (but defer) collection-level binding and decision→execution binding so consumers do not assume coverage that does not exist.

## 4. Non-goals (v1)

- Re-signing, wrapping, or replacing the native `AuditReceipt` format.
- A transparency log / blockchain for keys.
- Binding downstream tool *execution* into the decision receipt (separate workstream — §10).
- Designing Merkle leaf/root construction for manifests in this phase (record requirements only — §9).
- Changing `/v1/export` to embed full key material by default.
- Receipt schema bump for `keys_uri` / `jwks_uri` (stays in export metadata / verifier config — §7).

---

## 5. Durability claims (be precise)

| Phase | Source of published keys | Honest claim |
|-------|--------------------------|--------------|
| **v1** | Current key + `AEGIS_AUDIT_SIGNING_KEYS_HISTORY` (env) | **Independently publishable / retrievable** historical verification material. Can **disappear** on rebuild / config loss. **Not** “durable historical key custody.” |
| **v1.1** | Append-only Postgres `audit_signing_keys` (env remains bootstrap/import) | **Durable** historical key custody / publication that survives rebuilds. |

Do **not** call env-backed v1 “durable.” Reserve that word for v1.1.

Postgres history does **not** block the first JWKS ship, provided v1 docs stay honest about non-durability across loss/rebuild.

---

## 6. Proposed API

### 6.1 Opt-in public read

Key endpoints are **public-read only when an operator explicitly enables external verification** (e.g. `AEGIS_AUDIT_PUBLIC_KEYS=true`). **Off by default** — same network/auth posture as today for everything except `/health` / `/ready`.

Public keys are not secrets; authenticity of the **publication channel** (trust anchor, §2 / §8) is the important part.

### 6.2 `GET /v1/keys/{id}`

Return one public key by `signer_key_id` (`kid`).

**200 response (JWK, RFC 7517 OKP / Ed25519):**

```json
{
  "kty": "OKP",
  "crv": "Ed25519",
  "kid": "aegis-audit-2026-09",
  "x": "<base64url 32-byte public key>",
  "use": "sig",
  "alg": "EdDSA",
  "aegis_status": "active",
  "aegis_not_before": "2026-01-01T00:00:00Z"
}
```

**404** if `id` is unknown (fail closed).

### 6.3 `GET /v1/keys` (JWKS)

RFC 7517 JWKS listing current + all historical public keys known to this deployment.

```json
{
  "keys": [ /* JWK objects as above */ ]
}
```

Optional discovery alias (same body): `GET /.well-known/jwks.json`.

**Caching:** `Cache-Control: public, max-age=300` + `ETag`.

**`kid` mapping:** exactly `AuditReceipt.signer_key_id`. No silent remapping.

### 6.4 Rotation vs compromise (explicit semantics)

Define these **before** exposing `aegis_status`. They are different claims:

| Field / state | Meaning |
|---------------|---------|
| `aegis_status`: **`active`** | Permitted for **new** signing. |
| `aegis_status`: **`retired`** | **No longer** used for new signing; **historical signatures remain valid** to verify. |
| `aegis_compromised_at` (optional RFC3339) | Distinct compromise / revocation metadata. When set, verifiers may treat the key as untrusted for some or all historical windows per **their** policy. |

**Do not** let `retired` imply “all historical receipts signed by this key are now invalid.” That is a correctness bug waiting to happen.

Ordinary rotation → `retired` (+ optional `aegis_retired_at`). Compromise → separate `aegis_compromised_at` (v1 may omit until operators have a way to record it; v1.1 Postgres should support it).

---

## 7. `keys_uri`: export metadata only (no receipt schema bump)

| Channel | Role |
|---------|------|
| `GET /v1/keys` / `GET /v1/keys/{id}` | Publication / discovery of verification material |
| Export response **metadata** `keys_uri` | Convenience hint: “signer’s JWKS is advertised here” |
| Inside signed `AuditReceipt` | **Out of scope for v1** — no schema bump |

A URI inside a signed receipt can only claim “the signer *says* keys are here,” **not** “trust keys from here.” Trust configuration belongs to the **verifier** (trust anchor in §2 / §8), not the receipt.

---

## 8. Trust model for third parties

**Target offline path:**

1. Establish trust in the publisher (TLS hostname / deployment identity / out-of-band ceremony).
2. Fetch JWKS (or `GET /v1/keys/{id}`) through that trusted channel while keys are published.
3. **Pin** the exact public key material with the evidence package.
4. Later: verify each receipt offline via `signer_key_id` → pinned JWK `x`; no live AEGIS required.

JWKS does not invent a global PKI; it removes the “you had to be on the box to read the env” barrier.

BoundaryAttest (or similar) does **not** need to sit in the verification path if AEGIS ships this natively: receipt + independently trusted historical key publication is the stronger solution.

---

## 9. Future: `AuditExportManifest` (requirements only — do not design the root now)

Single receipt remains the atomic crypto unit.

When the manifest workstream starts, **fully specify** before shipping:

- **Leaf representation** — e.g. `leaf = SHA-256(<exact defined receipt representation>)`
- **Ordering rule** — explicit deterministic ordering of leaves
- **Root construction** — explicit Merkle (or other) construction

so two independent implementations compute the **same** commitment. Do **not** leave “Merkle root (or sorted SHA-256 concatenation)” as an open choice at implementation time.

**Narrower guarantee of a manifest:**

> This signer committed to **this exact set of receipts as this particular export**.

It does **not** prove “these are the only receipts that ever existed.” Completeness vs full audit history needs a **separate, stronger checkpoint / history mechanism** later.

**Phasing:** optional signed export manifest comes **after** v1 key publication and preferably after v1.1 durable keys — manifests cannot be independently verified long-term without trusted historical keys.

---

## 10. Decision receipt ≠ execution evidence

Make this explicit:

An AEGIS **decision receipt** proves a policy / tool-gate **decision was recorded and signed**. It does **not** prove that:

- the permitted action actually executed;
- the executed action matched the request;
- the returned result corresponds to that decision; or
- any external side effect occurred.

If execution evidence is modeled later, it must be a **separate evidence object** that **references** the decision receipt for correlation — **not** merged into the decision receipt.

Residual risk language in `audit/README.md` already points this way; keep JWKS / key publication scoped accordingly.

---

## 11. Locked sequencing & open-question answers

Adopted from the #63 external review (2026-09-20):

| Open question (original §10) | Locked answer |
|------------------------------|---------------|
| Key endpoint auth | **Public-read when operator opts in** to external verification; **not** on by default |
| Postgres before first JWKS? | **No** — does not block v1, if v1 is documented as not-yet-durable |
| Priority: keys vs manifest? | **Key publication first** |
| `keys_uri` placement | **Export metadata / verifier config**; no receipt schema change yet |

```text
v1      historical-key JWKS / public-key export
        + documented offline verification
        + active / retired / compromise field semantics
        + opt-in public read

v1.1    durable append-only key history (Postgres)

later   optional signed export manifest
        (leaf / order / root fully specified; narrow “this export” guarantee)

separate workstream
        decision → execution correlation
        (separate evidence object referencing decision receipt)
```

---

## 12. Migration / rollout (v1)

1. Handlers: `GET /v1/keys`, `GET /v1/keys/{id}`, optional `/.well-known/jwks.json`.
2. Build JWKS from current signer + `ParseHistoricalKeys`; `aegis_status` = `active` | `retired`; compromise field present in schema but optional until recorded.
3. Gate public access behind explicit operator opt-in env flag.
4. Tests: known kid → 200; unknown → 404; JWKS contains current + history; retired ≠ compromised.
5. Optional: `keys_uri` on export **metadata** only.
6. Update `audit/README.md` Known gaps; document offline verify recipe and non-durable v1 claim.
7. Follow-ups (not this PR): Postgres key history; manifest workstream; decision→execution design.

---

## 13. Acceptance criteria (v1 implementation)

- [ ] `GET /v1/keys/{id}` returns JWK for current and historical ids used in fixtures
- [ ] `GET /v1/keys` (JWKS) lists the same set; unknown id → 404
- [ ] `aegis_status` documents `active` vs `retired`; compromise is a separate field
- [ ] Public key routes require explicit opt-in; default remains authenticated / closed
- [ ] Documented offline verify recipe using exported receipts + fetched/pinned JWKS
- [ ] README Known gaps updated; durability wording honest for env-backed v1
- [ ] Explicit doc notes: decision≠execution; export bag≠manifest; JWKS≠trust anchor
