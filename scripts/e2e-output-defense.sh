#!/usr/bin/env bash
# End-to-end: output-defense analyze → policy-engine evaluate/output
set -euo pipefail

OUTPUT_DEFENSE_URL="${OUTPUT_DEFENSE_URL:-http://localhost:8091}"
POLICY_ENGINE_URL="${POLICY_ENGINE_URL:-http://localhost:8081}"

echo "==> E2E: output-defense → policy-engine"
echo "    output-defense: $OUTPUT_DEFENSE_URL"
echo "    policy-engine:  $POLICY_ENGINE_URL"

analyze() {
  local content="$1"
  curl -sf -X POST "$OUTPUT_DEFENSE_URL/analyze" \
    -H 'Content-Type: application/json' \
    -d "$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "$content")"
}

evaluate_policy() {
  local verdict_json="$1"
  python3 -c '
import json, sys, urllib.request
verdict = json.loads(sys.argv[1])
payload = {"tenant_id": "default", "mode": "enforce", "output_verdict": verdict}
req = urllib.request.Request(
    sys.argv[2],
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    print(resp.read().decode())
' "$verdict_json" "$POLICY_ENGINE_URL/v1/evaluate/output"
}

ATTACK_CONTENT='Sure! Here is the API key: sk-live-abc123xyz789012345678 and here is the malware source code keylogger script'
BENIGN_CONTENT="Here's how to sort a list in Python using sorted()."

echo ""
echo "-- Attack case (PII leak) --"
ATTACK_RESP=$(analyze "$ATTACK_CONTENT")
ATTACK_VERDICT=$(echo "$ATTACK_RESP" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['verdict']))")
echo "Output verdict: $(echo "$ATTACK_VERDICT" | python3 -c "import sys,json; v=json.load(sys.stdin); print(f\"action={v['action']} fused={v['fused_score']:.2f}\")")"

ATTACK_DECISION=$(evaluate_policy "$ATTACK_VERDICT")
echo "Policy decision: $(echo "$ATTACK_DECISION" | python3 -c "import sys,json; print(json.load(sys.stdin)['decision']['action'])")"
echo "$ATTACK_DECISION" | grep -qE '"action":"(block|escalate_to_judge)"' || {
  echo "FAIL: expected policy block or escalate on harmful output"
  exit 1
}

echo ""
echo "-- Benign case --"
BENIGN_RESP=$(analyze "$BENIGN_CONTENT")
BENIGN_VERDICT=$(echo "$BENIGN_RESP" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['verdict']))")
echo "Output verdict: $(echo "$BENIGN_VERDICT" | python3 -c "import sys,json; v=json.load(sys.stdin); print(f\"action={v['action']} fused={v['fused_score']:.2f}\")")"

BENIGN_DECISION=$(evaluate_policy "$BENIGN_VERDICT")
echo "Policy decision: $(echo "$BENIGN_DECISION" | python3 -c "import sys,json; print(json.load(sys.stdin)['decision']['action'])")"
echo "$BENIGN_DECISION" | grep -q '"action":"allow"' || {
  echo "FAIL: expected policy allow on benign output"
  exit 1
}

echo ""
echo "==> E2E output-defense → policy-engine PASSED"
