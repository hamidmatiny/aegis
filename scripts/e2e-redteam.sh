#!/usr/bin/env bash
# End-to-end: redteam campaign against live input-defense + output-defense
set -euo pipefail

REDTEAM_URL="${REDTEAM_URL:-http://localhost:8092}"
INPUT_DEFENSE_URL="${INPUT_DEFENSE_URL:-http://localhost:8090}"
OUTPUT_DEFENSE_URL="${OUTPUT_DEFENSE_URL:-http://localhost:8091}"

echo "==> E2E: red-team campaign against defense stack"
echo "    redteam:        $REDTEAM_URL"
echo "    input-defense:  $INPUT_DEFENSE_URL"
echo "    output-defense: $OUTPUT_DEFENSE_URL"

curl -sf "$INPUT_DEFENSE_URL/health" >/dev/null || { echo "FAIL: input-defense unreachable"; exit 1; }
curl -sf "$OUTPUT_DEFENSE_URL/health" >/dev/null || { echo "FAIL: output-defense unreachable"; exit 1; }
curl -sf "$REDTEAM_URL/health" >/dev/null || { echo "FAIL: redteam unreachable"; exit 1; }

echo ""
echo "-- Run identity-strategy campaign (subset for speed) --"
RESP=$(curl -sf -X POST "$REDTEAM_URL/v1/campaigns/run" \
  -H 'Content-Type: application/json' \
  -d '{"strategies":["identity"],"store_bypasses":true}')

CAMPAIGN_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['report']['campaign_id'])")
BYPASS_RATE=$(echo "$RESP" | python3 -c "import sys,json; r=json.load(sys.stdin)['report']; print(f\"{r['bypass_rate']:.3f}\")")
TOTAL=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['report']['total_probes'])")
BYPASSES=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['report']['bypass_count'])")

echo "Campaign: $CAMPAIGN_ID"
echo "Probes: $TOTAL | Bypasses: $BYPASSES | Bypass rate: $BYPASS_RATE"

echo "$RESP" | python3 -c "import sys,json; r=json.load(sys.stdin)['report'];
print('Input defense BR:', round(r['by_target']['input_defense']['bypass_rate'], 3));
print('Output defense BR:', round(r['by_target']['output_defense']['bypass_rate'], 3))"

echo ""
echo "-- Fetch campaign report --"
curl -sf "$REDTEAM_URL/v1/campaigns/$CAMPAIGN_ID" | python3 -c "import sys,json; r=json.load(sys.stdin); assert r['total_probes']>0"

echo ""
echo "-- List stored bypass patterns --"
PATTERN_COUNT=$(curl -sf "$REDTEAM_URL/v1/patterns" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['patterns']))")
echo "Stored patterns: $PATTERN_COUNT"

echo ""
echo "==> E2E red-team campaign PASSED"
