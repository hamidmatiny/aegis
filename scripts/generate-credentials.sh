#!/usr/bin/env bash
# Generates fresh, random dashboard credentials and a gateway API key, and
# writes them into .env (creating it from .env.example if needed). There is
# no static default credential anywhere in this repo by design — run this
# once before `docker compose up` to persist stable values across restarts.
set -euo pipefail

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

DASHBOARD_PASSWORD="$(random_hex 16)"
API_KEY="aegis_$(random_hex 32)"
AGENT_GATE_SERVICE_KEY="aegis_$(random_hex 32)"
AGENT_GATE_REVIEWER_KEY="aegis_$(random_hex 32)"

upsert_env "AEGIS_DASHBOARD_USER" "admin"
upsert_env "AEGIS_DASHBOARD_PASSWORD" "$DASHBOARD_PASSWORD"
upsert_env "AEGIS_API_KEYS" "$API_KEY"
upsert_env "AEGIS_AGENT_GATE_API_KEYS" "$AGENT_GATE_SERVICE_KEY"
upsert_env "AEGIS_AGENT_GATE_REVIEWER_KEYS" "$AGENT_GATE_REVIEWER_KEY"

cat <<MSG

Generated fresh credentials and wrote them to .env:

  Dashboard login:        admin / $DASHBOARD_PASSWORD
  Gateway API key:        $API_KEY
  Agent-gate service key: $AGENT_GATE_SERVICE_KEY   (calling agents use this)
  Agent-gate reviewer key: $AGENT_GATE_REVIEWER_KEY  (approve/deny only — deliberately
                                                       different from the service key so
                                                       an agent can never approve its own
                                                       irreversible action)

Keep these secret — .env is gitignored. Re-run this script any time to
rotate both. Use the API key against the gateway as:

  curl -H "Authorization: Bearer $API_KEY" http://localhost:8080/v1/chat/completions ...

MSG
