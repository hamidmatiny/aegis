#!/usr/bin/env bash
# E2E: dashboard UI + proxied backend APIs (with HTTP basic auth)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT/.env" && -z "${AEGIS_DASHBOARD_PASSWORD:-}" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:3000}"
DASHBOARD_USER="${AEGIS_DASHBOARD_USER:-admin}"
# No static default password. Set AEGIS_DASHBOARD_PASSWORD (see
# scripts/generate-credentials.sh, or check `docker compose logs dashboard`
# for a generated one-time password) before running this script.
: "${AEGIS_DASHBOARD_PASSWORD:?Set AEGIS_DASHBOARD_PASSWORD first — see scripts/generate-credentials.sh}"
DASHBOARD_PASSWORD="${AEGIS_DASHBOARD_PASSWORD}"
AUTH=(-u "${DASHBOARD_USER}:${DASHBOARD_PASSWORD}")

echo "==> E2E: AEGIS dashboard"
echo "    dashboard: $DASHBOARD_URL"

curl -sf "${AUTH[@]}" "$DASHBOARD_URL/" >/dev/null || { echo "FAIL: dashboard unreachable or auth rejected"; exit 1; }

echo ""
echo "-- Proxied audit health --"
curl -sf "${AUTH[@]}" "$DASHBOARD_URL/api/audit/health" | grep -q '"service":"audit"' || {
  echo "FAIL: audit proxy"
  exit 1
}

echo "-- Proxied policy pack detail --"
curl -sf "${AUTH[@]}" "$DASHBOARD_URL/api/policy/v1/policy-packs/default" | grep -q '"source_yaml"' || {
  echo "FAIL: policy pack proxy"
  exit 1
}

echo "-- Proxied approvals list --"
curl -sf "${AUTH[@]}" "$DASHBOARD_URL/api/agent-gate/v1/approvals" | grep -q '"approvals"' || {
  echo "FAIL: approvals proxy"
  exit 1
}

echo "-- Proxied redteam campaigns --"
curl -sf "${AUTH[@]}" "$DASHBOARD_URL/api/redteam/v1/campaigns" | grep -q '"campaigns"' || {
  echo "FAIL: campaigns proxy"
  exit 1
}

echo "-- Proxied agent-gate evaluate + decide (nginx must route decide to the reviewer key) --"
approval_id="$(curl -sf "${AUTH[@]}" -X POST "$DASHBOARD_URL/api/agent-gate/v1/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"default","tool_call":{"tool_name":"delete_database","risk_level":"IRREVERSIBLE","arguments":[{"name":"db_id","value":"e2e-test"}]}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["decision"].get("approval_request_id",""))')"
[[ -n "$approval_id" ]] || { echo "FAIL: proxied evaluate did not return an approval_request_id"; exit 1; }

curl -sf "${AUTH[@]}" -X POST "$DASHBOARD_URL/api/agent-gate/v1/approvals/${approval_id}/decide" \
  -H 'Content-Type: application/json' \
  -d '{"approved":true,"reviewer_id":"e2e-test"}' \
  | grep -q '"status":"APPROVED"' || {
  echo "FAIL: proxied decide did not approve — check dashboard/nginx.conf's decide regex location and that"
  echo "      AEGIS_AGENT_GATE_REVIEWER_KEYS matches between the dashboard and agent-gate containers"
  exit 1
}

echo ""
echo "PASS: dashboard E2E"
