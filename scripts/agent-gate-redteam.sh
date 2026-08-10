#!/usr/bin/env bash
# Adversarial probes against agent-gate's actual enforcement, not just its
# happy path. Each probe encodes a real gap found by manually red-teaming
# this service (see agent-gate/internal/auth and
# policy-engine/internal/engine/risk.go for the fixes) — this script is
# both the regression test for those fixes and a repeatable way to keep
# checking as the service evolves.
#
# Usage:
#   ./scripts/agent-gate-redteam.sh                    # against localhost:8083
#   AGENT_GATE_URL=http://<vm-ip>:8083 ./scripts/agent-gate-redteam.sh   # against a live deploy
#
# Requires AEGIS_AGENT_GATE_API_KEYS and AEGIS_AGENT_GATE_REVIEWER_KEYS to
# be set (sourced from .env if present and not already in the environment).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE_URL="${AGENT_GATE_URL:-http://localhost:8083}"

if [[ -f "$ROOT/.env" && ( -z "${AEGIS_AGENT_GATE_API_KEYS:-}" || -z "${AEGIS_AGENT_GATE_REVIEWER_KEYS:-}" ) ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

: "${AEGIS_AGENT_GATE_API_KEYS:?AEGIS_AGENT_GATE_API_KEYS must be set — run scripts/generate-credentials.sh, or export it}"
: "${AEGIS_AGENT_GATE_REVIEWER_KEYS:?AEGIS_AGENT_GATE_REVIEWER_KEYS must be set}"

SERVICE_KEY="${AEGIS_AGENT_GATE_API_KEYS%%,*}"
REVIEWER_KEY="${AEGIS_AGENT_GATE_REVIEWER_KEYS%%,*}"

PASS=0
FAIL=0

check() {
  local desc="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc (expected $want, got $got)"
    FAIL=$((FAIL + 1))
  fi
}

echo "==================================================================="
echo " agent-gate red team — target: $GATE_URL"
echo "==================================================================="

echo ""
echo "-- 1. Unauthenticated evaluate is rejected --"
status="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GATE_URL/v1/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"default","tool_call":{"tool_name":"search_docs","risk_level":"LOW"}}')"
check "no credentials at all" "$status" "401"

echo ""
echo "-- 2. Risk-level self-declaration for a catalogued tool doesn't bypass approval --"
echo "   (claiming LOW for delete_database — registered IRREVERSIBLE in policy-engine/policies/default.yaml)"
resp="$(curl -s -X POST "$GATE_URL/v1/evaluate" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${SERVICE_KEY}" \
  -d '{"tenant_id":"default","tool_call":{"tool_name":"delete_database","risk_level":"LOW","arguments":[{"name":"db_id","value":"redteam-probe"}]}}')"
status_field="$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",{}).get("status","?"))' 2>/dev/null || echo "?")"
approval_id="$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",{}).get("approval_request_id",""))' 2>/dev/null || echo "")"
overridden="$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",{}).get("risk_level_overridden",False))' 2>/dev/null || echo "False")"
check "understated risk still escalates to human approval" "$status_field" "AWAITING_HUMAN_APPROVAL"
check "response says the catalog overrode the declared risk" "$overridden" "True"
if [[ -z "$approval_id" ]]; then
  echo "  FAIL: no approval_request_id returned — can't run the self-approval probes below"
  FAIL=$((FAIL + 1))
else
  echo "  (approval_id: $approval_id)"
fi

if [[ -n "$approval_id" ]]; then
  echo ""
  echo "-- 3. The service key that submitted the call cannot approve it --"
  status="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GATE_URL/v1/approvals/${approval_id}/decide" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${SERVICE_KEY}" \
    -d '{"approved":true,"reviewer_id":"redteam-self-approve-attempt"}')"
  check "self-approval with the calling agent's own key is rejected" "$status" "401"

  echo ""
  echo "-- 4. Approving with no credentials at all is rejected --"
  status="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GATE_URL/v1/approvals/${approval_id}/decide" \
    -H 'Content-Type: application/json' \
    -d '{"approved":true,"reviewer_id":"redteam-anonymous-attempt"}')"
  check "unauthenticated decide is rejected" "$status" "401"

  echo ""
  echo "-- 5. The real reviewer key can approve it --"
  resp="$(curl -s -X POST "$GATE_URL/v1/approvals/${approval_id}/decide" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${REVIEWER_KEY}" \
    -d '{"approved":true,"reviewer_id":"redteam-script"}')"
  decided_status="$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",{}).get("status","?"))' 2>/dev/null || echo "?")"
  check "reviewer key approves successfully" "$decided_status" "APPROVED"

  echo ""
  echo "-- 6. Replaying the same decision (double-spend) is rejected --"
  status="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GATE_URL/v1/approvals/${approval_id}/decide" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${REVIEWER_KEY}" \
    -d '{"approved":false,"reviewer_id":"redteam-replay-attempt"}')"
  check "deciding an already-decided approval is rejected" "$status" "400"
fi

echo ""
echo "-- 7. Approval IDs are not sequential/predictable --"
id1="$(curl -s -X POST "$GATE_URL/v1/evaluate" -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${SERVICE_KEY}" \
  -d '{"tenant_id":"default","tool_call":{"tool_name":"delete_database","risk_level":"IRREVERSIBLE"}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["decision"]["approval_request_id"])' 2>/dev/null)"
id2="$(curl -s -X POST "$GATE_URL/v1/evaluate" -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${SERVICE_KEY}" \
  -d '{"tenant_id":"default","tool_call":{"tool_name":"delete_database","risk_level":"IRREVERSIBLE"}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["decision"]["approval_request_id"])' 2>/dev/null)"
if [[ -n "$id1" && -n "$id2" && "$id1" != "$id2" && "${#id1}" -ge 21 ]]; then
  echo "  PASS: two approval IDs are distinct and long enough to be random ($id1, $id2)"
  PASS=$((PASS + 1))
else
  echo "  FAIL: approval IDs look short or non-random ($id1, $id2)"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "-- 8. Documented trust boundary: an unregistered tool is NOT overridden --"
echo "   (this should PASS as 'allowed' — it documents where the catalog doesn't reach, not a bug)"
resp="$(curl -s -X POST "$GATE_URL/v1/evaluate" -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${SERVICE_KEY}" \
  -d '{"tenant_id":"default","tool_call":{"tool_name":"some_unregistered_tool","risk_level":"LOW"}}')"
status_field="$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",{}).get("status","?"))' 2>/dev/null || echo "?")"
check "unregistered tool falls back to declared risk_level (register it in tool_catalog if that's wrong)" "$status_field" "APPROVED"

echo ""
echo "==================================================================="
echo " $PASS passed, $FAIL failed"
echo "==================================================================="
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
