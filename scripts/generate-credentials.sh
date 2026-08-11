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

fill "AEGIS_DASHBOARD_USER" "echo admin"
fill "AEGIS_DASHBOARD_PASSWORD" "random_hex 16"
fill "AEGIS_API_KEYS" "echo aegis_\$(random_hex 32)"
fill "AEGIS_AGENT_GATE_API_KEYS" "echo aegis_\$(random_hex 32)"
fill "AEGIS_AGENT_GATE_REVIEWER_KEYS" "echo aegis_\$(random_hex 32)"

# --- Added: three secrets that used to ship on public, unrotated
# defaults from .env.example (found during a security review) ---

# Redis has no service wired up to it yet, so this is a plain fill(): a
# brand-new var, nothing currently reads REDIS_URL, no sync risk.
fill "REDIS_PASSWORD" "random_hex 20"

# The audit signing key ships with a real-looking default
# (base64 of the literal string "aegis-dev-audit-signing-key-v1!!") that
# a plain fill() would never touch since it's never empty.
fill_if_default "AEGIS_AUDIT_SIGNING_KEY" "random_b64 32" "YWVnaXMtZGV2LWF1ZGl0LXNpZ25pbmcta2V5LXYxISE="

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
