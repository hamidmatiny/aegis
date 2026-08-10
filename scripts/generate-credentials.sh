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

current_value() {
  # Prints the current value of $1 in .env, or empty if unset/commented out.
  grep "^${1}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-
}

upsert_env() {
  local key="$1" value="$2" tmp
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" -F= 'BEGIN{OFS="="} $1==k{print k,v; next} {print}' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  elif grep -q "^# ${key}=" "$ENV_FILE" 2>/dev/null; then
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" -F= 'BEGIN{OFS="="} $0=="# "k"="{print k,v; next} {print}' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

# fill KEY [default-value]: writes a fresh random value only if the
# variable is unset/empty in .env, or always if --rotate was passed.
fill() {
  local key="$1" generator="$2"
  if [ "$ROTATE" = true ] || [ -z "$(current_value "$key")" ]; then
    upsert_env "$key" "$(eval "$generator")"
  fi
}

fill "AEGIS_DASHBOARD_USER" "echo admin"
fill "AEGIS_DASHBOARD_PASSWORD" "random_hex 16"
fill "AEGIS_API_KEYS" "echo aegis_\$(random_hex 32)"
fill "AEGIS_AGENT_GATE_API_KEYS" "echo aegis_\$(random_hex 32)"
fill "AEGIS_AGENT_GATE_REVIEWER_KEYS" "echo aegis_\$(random_hex 32)"

DASHBOARD_PASSWORD="$(current_value AEGIS_DASHBOARD_PASSWORD)"
API_KEY="$(current_value AEGIS_API_KEYS)"
AGENT_GATE_SERVICE_KEY="$(current_value AEGIS_AGENT_GATE_API_KEYS)"
AGENT_GATE_REVIEWER_KEY="$(current_value AEGIS_AGENT_GATE_REVIEWER_KEYS)"

cat <<MSG

.env credentials (existing values kept as-is; only missing ones were generated
— pass --rotate to force fresh values for everything):

  Dashboard login:         admin / $DASHBOARD_PASSWORD
  Gateway API key:         $API_KEY
  Agent-gate service key:  $AGENT_GATE_SERVICE_KEY   (calling agents use this)
  Agent-gate reviewer key: $AGENT_GATE_REVIEWER_KEY   (approve/deny only — deliberately
                                                        different from the service key so
                                                        an agent can never approve its own
                                                        irreversible action)

Keep these secret — .env is gitignored. Use the API key against the
gateway as:

  curl -H "Authorization: Bearer $API_KEY" http://localhost:8080/v1/chat/completions ...

MSG
