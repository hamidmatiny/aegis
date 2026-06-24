#!/usr/bin/env bash
# End-to-end: write signed audit receipt → verify → query → export
set -euo pipefail

AUDIT_URL="${AUDIT_URL:-http://localhost:8084}"

echo "==> E2E: audit signed receipts"
echo "    audit: $AUDIT_URL"

curl -sf "$AUDIT_URL/health" >/dev/null || { echo "FAIL: audit unreachable"; exit 1; }

echo ""
echo "-- Write input-defense receipt --"
WRITE=$(curl -sf -X POST "$AUDIT_URL/v1/receipts" \
  -H 'Content-Type: application/json' \
  -d '{
    "event_type": "INPUT_DEFENSE",
    "tenant_id": "default",
    "trace": {"trace_id": "e2e-trace-1", "request_id": "e2e-req-1"},
    "input_verdict": {"action": "BLOCK", "fused_score": 0.93},
    "policy_pack_id": "default",
    "policy_pack_version": "1.0.0"
  }')

RECEIPT_ID=$(echo "$WRITE" | python3 -c "import sys,json; print(json.load(sys.stdin)['receipt_id'])")
echo "Receipt: $RECEIPT_ID"

echo ""
echo "-- Verify signature --"
VERIFY=$(curl -sf "$AUDIT_URL/v1/receipts/$RECEIPT_ID/verify")
echo "$VERIFY" | python3 -c "import sys,json; v=json.load(sys.stdin); assert v['valid'], v.get('reason','invalid')"

echo ""
echo "-- Query by tenant --"
COUNT=$(curl -sf "$AUDIT_URL/v1/receipts?tenant_id=default&limit=10" \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin)['receipts']))")
if [ "$COUNT" -lt 1 ]; then
  echo "FAIL: expected at least 1 receipt in query"
  exit 1
fi
echo "Query returned $COUNT receipt(s)"

echo ""
echo "-- Export JSON bundle --"
EXPORT=$(curl -sf -X POST "$AUDIT_URL/v1/export" \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"default","format":"json"}')
echo "$EXPORT" | python3 -c "import sys,json; data=json.load(sys.stdin); assert len(data)>=1"

echo ""
echo "==> E2E audit service PASSED"
