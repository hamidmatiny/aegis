#!/usr/bin/env bash
# Fills in any missing credentials in .env (creating it from .env.example
# if needed) with fresh random values. There is no static default
# credential anywhere in this repo by design.
#
# Default behavior is a BACKFILL, not a rotation: a variable that already
# has a non-empty value in .env is left alone. This makes it safe to call
# unconditionally from setup.sh on every redeploy, including when a new
# required variable is added later (as happened when the agent-gate
# service/reviewer keys were introduced) without silently rotating
# credentials that were already in use.
#
# Pass --rotate to force fresh values for everything instead.
set -euo pipefail

ROTATE=false
if [ "${1:-}" = "--rotate" ]; then
  ROTATE=true
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
EXAMPLE_FILE="$ROOT/.env.example"

if [ ! -f "$ENV_FILE" ]; then
  cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo "Created .env from .env.example"
fi

random_hex() {
  local bytes="$1"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  else
    head -c "$bytes" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

# random_b64 BYTES: base64-encoded random bytes. Used for
# AEGIS_AUDIT_SIGNING_KEY, which the audit service parses as a raw
# Ed25519 seed (32 bytes) once base64-decoded — see
# audit/internal/signer/signer.go's parseKeyMaterial. Plain hex won't
# work here; it has to be base64.
random_b64() {
  local bytes="$1"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 "$bytes"
  else
    head -c "$bytes" /dev/urandom | base64
  fi
}

current_value() {
  # Prints the current value of $1 in .env, or empty if unset/commented out.
  # The trailing `|| true` matters under `set -o pipefail`: grep exits 1
  # when the key isn't found yet (the common case for a brand-new var),
  # and without this, that non-zero status would propagate out of a plain
  # `x="$(current_value ...)"` assignment and trip `set -e`, killing the
  # whole script -- even though "key not found yet" isn't actually an
  # error here, just an empty result.
  grep "^${1}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || true
}

upsert_env() {
  local key="$1" value="$2" tmp
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" -F= 'BEGIN{OFS="="} $1==k{print k,v; next} {print}' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  elif grep -q "^# ${key}=" "$ENV_FILE" 2>/dev/null; then
    tmp="$(mktemp)"
    # Match on PREFIX ("# KEY=" followed by anything), not an exact
    # full-line match -- a commented placeholder that ships with a real
    # default value after the "=" (e.g. "# KEY=some-default-value", as
    # .env.example uses for AEGIS_AUDIT_SIGNING_KEY) would never match
    # the old $0=="# "k"=" exact comparison, so it silently never got
    # uncommented/replaced. index() here matches on prefix instead.
    awk -v k="$key" -v v="$value" -v prefix="# ${key}=" \
      'BEGIN{OFS="="} index($0, prefix) == 1 {print k,v; next} {print}' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

# fill KEY GENERATOR: writes a fresh random value only if the variable is
# unset/empty in .env, or always if --rotate was passed.
fill() {
  local key="$1" generator="$2"
  if [ "$ROTATE" = true ] || [ -z "$(current_value "$key")" ]; then
    upsert_env "$key" "$(eval "$generator")"
  fi
}

# fill_if_default KEY GENERATOR KNOWN_DEFAULT: like fill(), but also
# rotates when the current value still exactly matches a known public
# placeholder — not just when it's empty. Needed for variables that ship
# with a real-looking (but public, in .env.example) default value rather
# than being unset, where a plain emptiness check would never catch them.
fill_if_default() {
  local key="$1" generator="$2" known_default="$3" current
  current="$(current_value "$key")"
  if [ "$ROTATE" = true ] || [ -z "$current" ] || [ "$current" = "$known_default" ]; then
    upsert_env "$key" "$(eval "$generator")"
  fi
}

# derive_ed25519_pubkey_from_seed_b64 SEED_B64: prints the base64-encoded
# 32-byte Ed25519 public key derived from a base64-encoded 32-byte seed
# (the format AEGIS_AUDIT_SIGNING_KEY is stored in). Used only when
# rotating the audit signing key, to snapshot the outgoing key's public
# half into AEGIS_AUDIT_SIGNING_KEYS_HISTORY before it's overwritten --
# only the public key is ever needed to verify old receipts, so the
# private half is safely discarded once we have this.
#
# Works by wrapping the raw seed in the fixed, well-known 16-byte DER
# prefix for an unencrypted PKCS8 Ed25519 private key (RFC 8410 -- every
# such key has this exact prefix, since nothing about it varies except
# the seed), letting openssl derive the public key from that, then
# stripping openssl's own fixed 12-byte SubjectPublicKeyInfo prefix to
# recover the raw 32-byte public key. Deliberately avoids xxd (not
# guaranteed present on a minimal cloud image) -- the DER prefix is
# written directly via printf octal escapes, and the seed/output are
# handled as raw bytes via base64/tail, both already used elsewhere in
# this script.
derive_ed25519_pubkey_from_seed_b64() {
  local seed_b64="$1" tmp_der tmp_pub result
  tmp_der="$(mktemp)"
  tmp_pub="$(mktemp)"
  { printf '\060\056\002\001\000\060\005\006\003\053\145\160\004\042\004\040'
    printf '%s' "$seed_b64" | base64 -d; } > "$tmp_der" 2>/dev/null
  if [ "$(wc -c < "$tmp_der")" -ne 48 ]; then
    rm -f "$tmp_der" "$tmp_pub"
    echo "ERROR: AEGIS_AUDIT_SIGNING_KEY is not a 32-byte base64 seed -- cannot derive its public key" >&2
    return 1
  fi
  if ! openssl pkey -inform DER -in "$tmp_der" -pubout -outform DER -out "$tmp_pub" 2>/dev/null; then
    rm -f "$tmp_der" "$tmp_pub"
    echo "ERROR: openssl could not derive the Ed25519 public key from AEGIS_AUDIT_SIGNING_KEY" >&2
    return 1
  fi
  result="$(tail -c 32 "$tmp_pub" | base64)"
  rm -f "$tmp_der" "$tmp_pub"
  printf '%s' "$result"
}

fill "AEGIS_DASHBOARD_USER" "echo admin"
fill "AEGIS_DASHBOARD_PASSWORD" "random_hex 16"
fill "AEGIS_API_KEYS" "echo aegis_\$(random_hex 32)"
fill "AEGIS_AGENT_GATE_API_KEYS" "echo aegis_\$(random_hex 32)"
fill "AEGIS_AGENT_GATE_REVIEWER_KEYS" "echo aegis_\$(random_hex 32)"

# Shared internal service-to-service token: policy-engine, audit,
# input-defense, and output-defense now refuse to start without it, and
# every process that calls them (gateway, agent-gate, redteam, the
# dashboard's nginx proxy) needs the SAME value. Unlike the per-service
# keys above, there is no ephemeral-generate-if-missing fallback for this
# one anywhere in the code -- a value generated independently by each
# process would just disagree with every other process's copy and break
# every internal call, so it has to be filled here, once, and shared via
# .env like POSTGRES_PASSWORD is.
fill "AEGIS_INTERNAL_TOKEN" "echo aegis_internal_\$(random_hex 32)"

# --- Added: three secrets that used to ship on public, unrotated
# defaults from .env.example (found during a security review) ---

# Redis has no service wired up to it yet, so this is a plain fill(): a
# brand-new var, nothing currently reads REDIS_URL, no sync risk.
fill "REDIS_PASSWORD" "random_hex 20"

# The audit signing key ships with a real-looking default
# (base64 of the literal string "aegis-dev-audit-signing-key-v1!!") that
# a plain fill() would never touch since it's never empty. Rotating this
# key is more delicate than the others: every already-signed audit
# receipt records which key id signed it, and verification fails for any
# receipt whose key id the audit service doesn't recognize (see
# audit/internal/signer/signer.go). So before overwriting a REAL,
# already-in-use key (not the known public dev default below -- that
# one's public key was never secret to begin with, nothing to preserve),
# snapshot its public key into AEGIS_AUDIT_SIGNING_KEYS_HISTORY and roll
# AEGIS_AUDIT_SIGNING_KEY_ID to a fresh value, so old receipts stay
# verifiable after rotation.
AUDIT_KEY_DEFAULT="YWVnaXMtZGV2LWF1ZGl0LXNpZ25pbmcta2V5LXYxISE="
CURRENT_AUDIT_KEY="$(current_value AEGIS_AUDIT_SIGNING_KEY)"
AUDIT_KEY_ROTATION_BLOCKED=false
if [ "$ROTATE" = true ] || [ -z "$CURRENT_AUDIT_KEY" ] || [ "$CURRENT_AUDIT_KEY" = "$AUDIT_KEY_DEFAULT" ]; then
  if [ -n "$CURRENT_AUDIT_KEY" ] && [ "$CURRENT_AUDIT_KEY" != "$AUDIT_KEY_DEFAULT" ]; then
    OUTGOING_KEY_ID="$(current_value AEGIS_AUDIT_SIGNING_KEY_ID)"
    OUTGOING_KEY_ID="${OUTGOING_KEY_ID:-dev-key-1}"
    if OUTGOING_PUB="$(derive_ed25519_pubkey_from_seed_b64 "$CURRENT_AUDIT_KEY")"; then
      CURRENT_HISTORY="$(current_value AEGIS_AUDIT_SIGNING_KEYS_HISTORY)"
      NEW_HISTORY_ENTRY="${OUTGOING_KEY_ID}:${OUTGOING_PUB}"
      if [ -z "$CURRENT_HISTORY" ]; then
        upsert_env "AEGIS_AUDIT_SIGNING_KEYS_HISTORY" "$NEW_HISTORY_ENTRY"
      else
        upsert_env "AEGIS_AUDIT_SIGNING_KEYS_HISTORY" "${CURRENT_HISTORY},${NEW_HISTORY_ENTRY}"
      fi
      upsert_env "AEGIS_AUDIT_SIGNING_KEY_ID" "audit-key-$(date +%Y%m%d)-$(random_hex 4)"
      echo "NOTE: AEGIS_AUDIT_SIGNING_KEY is being rotated. The outgoing key" >&2
      echo "      (id: ${OUTGOING_KEY_ID}) was preserved in AEGIS_AUDIT_SIGNING_KEYS_HISTORY" >&2
      echo "      so previously-signed audit receipts stay verifiable." >&2
    else
      echo "ERROR: could not derive the outgoing audit signing key's public key -- refusing" >&2
      echo "       to rotate it, since that would break verification of every receipt" >&2
      echo "       already signed with it. Leaving AEGIS_AUDIT_SIGNING_KEY and" >&2
      echo "       AEGIS_AUDIT_SIGNING_KEY_ID untouched; everything else was still updated." >&2
      AUDIT_KEY_ROTATION_BLOCKED=true
    fi
  fi
  if [ "$AUDIT_KEY_ROTATION_BLOCKED" != true ]; then
    upsert_env "AEGIS_AUDIT_SIGNING_KEY" "$(random_b64 32)"
  fi
fi

# Postgres is the trickiest of the three: POSTGRES_PASSWORD and
# DATABASE_URL both ship with the same public default (aegis_dev) baked
# in, and DATABASE_URL embeds the password inline — so they have to be
# rotated together or the audit service won't be able to connect. We only
# touch this pair when DATABASE_URL still points at the bundled postgres
# service on its known default password; if it's been customized to point
# at an external database, we leave both alone rather than risk breaking
# a real connection string.
CURRENT_PG_PASSWORD="$(current_value POSTGRES_PASSWORD)"
CURRENT_DB_URL="$(current_value DATABASE_URL)"
if [ "$ROTATE" = true ] || [ -z "$CURRENT_PG_PASSWORD" ] || [ "$CURRENT_PG_PASSWORD" = "aegis_dev" ]; then
  if [ -z "$CURRENT_DB_URL" ] || printf '%s' "$CURRENT_DB_URL" | grep -q "aegis_dev"; then
    NEW_PG_PASSWORD="$(random_hex 20)"
    PG_USER="$(current_value POSTGRES_USER)"; PG_USER="${PG_USER:-aegis}"
    PG_DB="$(current_value POSTGRES_DB)"; PG_DB="${PG_DB:-aegis}"
    upsert_env "POSTGRES_PASSWORD" "$NEW_PG_PASSWORD"
    upsert_env "DATABASE_URL" "postgres://${PG_USER}:${NEW_PG_PASSWORD}@postgres:5432/${PG_DB}?sslmode=disable"
    echo "NOTE: POSTGRES_PASSWORD/DATABASE_URL were rotated in .env. If postgres" >&2
    echo "      already has data (a live/redeployed instance, not a fresh one)," >&2
    echo "      the running database does NOT pick this up automatically --" >&2
    echo "      POSTGRES_PASSWORD only takes effect on a container's first init." >&2
    echo "      Apply it to the live database with:" >&2
    echo "        docker compose exec postgres psql -U ${PG_USER} -c \"ALTER USER ${PG_USER} WITH PASSWORD '${NEW_PG_PASSWORD}';\"" >&2
  else
    echo "NOTE: DATABASE_URL looks customized (doesn't contain the known default)" >&2
    echo "      -- leaving POSTGRES_PASSWORD and DATABASE_URL untouched." >&2
  fi
fi

DASHBOARD_PASSWORD="$(current_value AEGIS_DASHBOARD_PASSWORD)"
API_KEY="$(current_value AEGIS_API_KEYS)"
AGENT_GATE_SERVICE_KEY="$(current_value AEGIS_AGENT_GATE_API_KEYS)"
AGENT_GATE_REVIEWER_KEY="$(current_value AEGIS_AGENT_GATE_REVIEWER_KEYS)"
INTERNAL_TOKEN="$(current_value AEGIS_INTERNAL_TOKEN)"
REDIS_PW="$(current_value REDIS_PASSWORD)"
PG_PW_DISPLAY="$(current_value POSTGRES_PASSWORD)"

cat <<MSG

.env credentials (existing values kept as-is; only missing/defaulted ones were
generated — pass --rotate to force fresh values for everything):

  Dashboard login:         admin / $DASHBOARD_PASSWORD
  Gateway API key:         $API_KEY
  Agent-gate service key:  $AGENT_GATE_SERVICE_KEY   (calling agents use this)
  Agent-gate reviewer key: $AGENT_GATE_REVIEWER_KEY   (approve/deny only — deliberately
                                                        different from the service key so
                                                        an agent can never approve its own
                                                        irreversible action)
  Internal service token:  $INTERNAL_TOKEN   (shared by policy-engine/audit/input-defense/
                                              output-defense and everything that calls them —
                                              same value everywhere, do not regenerate on
                                              just one service)
  Postgres password:       $PG_PW_DISPLAY
  Redis password:          $REDIS_PW   (not wired into any service yet, reserved)
  Audit signing key:       (regenerated if it was still the public dev default;
                            see AEGIS_AUDIT_SIGNING_KEY in .env — not printed here
                            since, unlike the others, it's a real cryptographic
                            signing key, not just an access credential)

Keep these secret — .env is gitignored. Use the API key against the
gateway as:

  curl -H "Authorization: Bearer $API_KEY" http://localhost:8080/v1/chat/completions ...

If POSTGRES_PASSWORD/DATABASE_URL were just rotated on an already-running
instance, see the ALTER USER note printed above -- the env var alone will
not change a live database's actual password.

MSG

# --- Stage B.1: encrypted backup of .env, via SOPS+age (opt-in, additive) ---
#
# Skipped entirely, silently, unless BOTH tools are installed AND
# .sops.yaml has a real age recipient configured (not the placeholder) --
# so this never disrupts a fresh install, CI, or anyone who hasn't opted
# into it yet. See .sops.yaml for the one-time setup (age-keygen, etc.),
# which is deliberately not something this script does on your behalf --
# the private key must never pass through a script or a chat.
if command -v sops >/dev/null 2>&1 && command -v age >/dev/null 2>&1    && [ -f "$ROOT/.sops.yaml" ]    && ! grep -q "REPLACE_WITH_YOUR_AGE_PUBLIC_KEY" "$ROOT/.sops.yaml"; then
  echo "==> Updating encrypted credential backup (.env.enc)..."
  if sops --input-type dotenv --output-type dotenv --encrypt "$ENV_FILE" > "$ENV_FILE.enc.tmp" 2>/tmp/sops-encrypt.err; then
    mv "$ENV_FILE.enc.tmp" "$ENV_FILE.enc"
    echo "    .env.enc updated. It's safe to commit (ciphertext) -- 'git add .env.enc'"
    echo "    when you're ready. This is your recovery path if .env is ever lost;"
    echo "    see scripts/decrypt-credentials.sh."
  else
    echo "WARNING: sops encryption failed, .env.enc NOT updated:" >&2
    cat /tmp/sops-encrypt.err >&2
    rm -f "$ENV_FILE.enc.tmp"
  fi
  rm -f /tmp/sops-encrypt.err
else
  echo "==> Skipping encrypted .env backup (sops/age not installed, or .sops.yaml"
  echo "    still has its placeholder key) -- see .sops.yaml to set this up."
fi
