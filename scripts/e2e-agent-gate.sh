#!/usr/bin/env bash
# End-to-end: agent-gate evaluate → policy-engine (real services)
set -euo pipefail

AGENT_GATE_URL="${AGENT_GATE_URL:-http://localhost:8083}"
POLICY_ENGINE_URL="${POLICY_ENGINE_URL:-http://localhost:8081}"

echo "==> E2E: agent-gate → policy-engine"
echo "    agent-gate:     $AGENT_GATE_URL"
echo "    policy-engine:  $POLICY_ENGINE_URL"

evaluate() {
  local payload="$1"
  curl -sf -X POST "$AGENT_GATE_URL/v1/evaluate" \
    -H 'Content-Type: application/json' \
    -d "$payload"
}

echo ""
echo "-- Benign tool call (should APPROVE) --"
BENIGN=$(evaluate '{
  "tenant_id": "default",
  "mode": "enforce",
  "tool_call": {
    "tool_name": "search_docs",
    "risk_level": "LOW",
    "arguments": [{"name": "query", "value": "deployment guide"}]
  }
}')
echo "$BENIGN" | grep -q '"status":"APPROVED"' || {
  echo "FAIL: expected APPROVED for benign tool call"
  echo "$BENIGN"
  exit 1
}
echo "Status: APPROVED"

echo ""
echo "-- Tainted credentials (should DENY via policy) --"
DENIED=$(evaluate '{
  "tenant_id": "default",
  "mode": "enforce",
  "tool_call": {
    "tool_name": "send_email",
    "risk_level": "MEDIUM",
    "arguments": [{
      "name": "body",
      "value": "attached password: hunter2",
      "taint_level": "TAINTED",
      "contains_credentials": true
    }]
  }
}')
echo "$DENIED" | grep -q '"status":"DENIED"' || {
  echo "FAIL: expected DENIED for tainted credentials"
  echo "$DENIED"
  exit 1
}
echo "Status: DENIED"

echo ""
echo "-- Irreversible action (should require human approval) --"
PENDING=$(evaluate '{
  "tenant_id": "default",
  "mode": "enforce",
  "tool_call": {
    "tool_name": "delete_production_database",
    "risk_level": "IRREVERSIBLE",
    "arguments": [{"name": "db_id", "value": "prod-primary"}]
  }
}')
APPR_ID=$(echo "$PENDING" | python3 -c "import sys,json; print(json.load(sys.stdin)['decision']['approval_request_id'])")
echo "$PENDING" | grep -q '"status":"AWAITING_HUMAN_APPROVAL"' || {
  echo "FAIL: expected AWAITING_HUMAN_APPROVAL"
  echo "$PENDING"
  exit 1
}
echo "Status: AWAITING_HUMAN_APPROVAL (id=$APPR_ID)"

echo ""
echo "-- Human approves pending request --"
APPROVED=$(curl -sf -X POST "$AGENT_GATE_URL/v1/approvals/$APPR_ID/decide" \
  -H 'Content-Type: application/json' \
  -d '{"approved": true, "reviewer_id": "admin@example.com", "comment": "Emergency maintenance approved"}')
echo "$APPROVED" | grep -q '"status":"APPROVED"' || {
  echo "FAIL: expected APPROVED after human decision"
  echo "$APPROVED"
  exit 1
}
echo "Status: APPROVED after human review"

echo ""
echo "==> E2E agent-gate → policy-engine PASSED"
