#!/usr/bin/env bash
# Smoke-test all Stage 11 example apps against a running local stack
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/examples/.e2e-venv"

echo "==> E2E: example apps"
echo "    root: $ROOT"

curl -sf http://localhost:8080/health >/dev/null || { echo "FAIL: gateway"; exit 1; }
curl -sf http://localhost:8083/health >/dev/null || { echo "FAIL: agent-gate"; exit 1; }

python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -e "$ROOT/sdk/python" httpx

run() {
  echo ""
  echo "-- $1 --"
  shift
  "$@"
}

run "chatbot benign" python "$ROOT/examples/chatbot/chatbot.py" --demo benign | grep -q "RESULT: ALLOWED"
run "chatbot injection" python "$ROOT/examples/chatbot/chatbot.py" --demo injection | grep -q "RESULT: BLOCKED"
run "rag benign" python "$ROOT/examples/rag-taint/rag_taint.py" --scenario benign-rag | grep -q "RESULT: ALLOWED"
run "rag injection" python "$ROOT/examples/rag-taint/rag_taint.py" --scenario injection-rag | grep -q "RESULT: BLOCKED"
run "rag taint exfil" python "$ROOT/examples/rag-taint/rag_taint.py" --scenario taint-exfil | grep -q "RESULT: DENIED"
run "tool safe" python "$ROOT/examples/tool-agent/tool_agent.py" --scenario safe-search | grep -q "RESULT: APPROVED"
run "tool approval" python "$ROOT/examples/tool-agent/tool_agent.py" --scenario irreversible-delete | grep -q "AWAITING_HUMAN_APPROVAL"
run "tool credential leak" python "$ROOT/examples/tool-agent/tool_agent.py" --scenario credential-leak | grep -q "RESULT: DENIED"

echo ""
echo "PASS: example apps E2E"
