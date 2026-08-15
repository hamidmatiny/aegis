#!/usr/bin/env bash
# Chaos / fault-injection test: automates FAILURE_MODES.md's own
# "Verification" section, which currently describes this as a manual
# procedure ("stop one decision dependency at a time and confirm...").
# This script does exactly that against the real running stack instead
# of leaving it as a step nobody reliably remembers to run by hand.
#
# For each decision-path dependency (input-defense, output-defense,
# policy-engine, model-router), stops the real container, confirms the
# gateway's defended chat pipeline fails CLOSED (502/500, never a
# released response), then restores it and confirms recovery before
# moving to the next one. policy-engine's scenario additionally checks
# agent-gate's /v1/evaluate, since agent-gate depends on policy-engine
# for every tool decision.
#
# For audit -- documented as deliberately NOT a decision dependency --
# confirms the opposite: the gateway chat pipeline keeps working (fails
# OPEN) with audit down, per FAILURE_MODES.md's explicit fail-open table.
#
# This is pass/fail correctness against a contract this repo already
# publishes, not a timing/load measurement (contrast scripts/benchmark.sh),
# so unlike that script this one is meant to gate CI -- a regression here
# is a real break of a documented security invariant.
set -uo pipefail  # deliberately not -e: assertions must all run and report, not stop at the first failure

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

# Local dev convenience: same .env auto-source as scripts/integration and
# scripts/benchmark.sh.
if [[ -f "$ROOT/.env" && ( -z "${AEGIS_API_KEYS:-}" || -z "${AEGIS_AGENT_GATE_API_KEYS:-}" ) ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

: "${AEGIS_API_KEYS:?AEGIS_API_KEYS must be set for chaos tests}"
: "${AEGIS_AGENT_GATE_API_KEYS:?AEGIS_AGENT_GATE_API_KEYS must be set for chaos tests}"

API_KEY="${AEGIS_API_KEYS%%,*}"
AGENT_GATE_KEY="${AEGIS_AGENT_GATE_API_KEYS%%,*}"

# service|health-URL -- pipe-delimited, not an associative array, since
# this needs to run under macOS's stock bash (3.2, no assoc arrays),
# same portability lesson as scripts/integration's own services list.
health_urls=(
  "input-defense|http://localhost:8090/health"
  "output-defense|http://localhost:8091/health"
  "policy-engine|http://localhost:8081/health"
  "model-router|http://localhost:8082/health"
  "audit|http://localhost:8084/health"
)

health_url_for() {
  local svc="$1" entry
  for entry in "${health_urls[@]}"; do
    if [[ "${entry%%|*}" == "$svc" ]]; then
      echo "${entry##*|}"
      return 0
    fi
  done
  return 1
}

FAILURES=0
STOPPED=""  # currently-stopped service, so the EXIT trap can restore on any early exit

restore_stopped() {
  if [[ -n "$STOPPED" ]]; then
    echo "==> Restoring $STOPPED"
    $COMPOSE start "$STOPPED" >/dev/null 2>&1
    wait_healthy "$STOPPED"
    STOPPED=""
  fi
}
trap restore_stopped EXIT

wait_healthy() {
  local svc="$1" url tries=30 i
  url="$(health_url_for "$svc")" || { echo "  WARN: no health URL known for $svc"; return 0; }
  for ((i = 0; i < tries; i++)); do
    curl -sf "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "  WARN: $svc did not become healthy again within ${tries}s"
}

chat_status() {
  curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8080/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${API_KEY}" \
    -d '{"model":"mock-model","messages":[{"role":"user","content":"Hello"}]}'
}

evaluate_status() {
  curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8083/v1/evaluate \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${AGENT_GATE_KEY}" \
    -d '{"tenant_id":"default","tool_call":{"tool_name":"search_docs","risk_level":"LOW","agent_id":"chaos-test-agent"}}'
}

assert_status() {
  local desc="$1" got="$2" want_pattern="$3"
  if [[ "$got" =~ $want_pattern ]]; then
    echo "  PASS: $desc (got $got)"
  else
    echo "  FAIL: $desc (got $got, expected pattern $want_pattern)"
    FAILURES=$((FAILURES + 1))
  fi
}

stop_service() {
  local svc="$1"
  if ! $COMPOSE stop "$svc" >/dev/null 2>&1; then
    echo "ERROR: could not stop $svc -- the chaos harness itself is broken, not a slow service" >&2
    exit 1
  fi
  STOPPED="$svc"
  sleep 1  # let the port actually go down; `docker compose stop` isn't instant
}

echo "==> Sanity check: full stack up, gateway chat + agent-gate evaluate both succeed"
assert_status "gateway chat succeeds with full stack up" "$(chat_status)" '^200$'
assert_status "agent-gate evaluate succeeds with full stack up" "$(evaluate_status)" '^200$'

for svc in input-defense output-defense policy-engine model-router; do
  echo "==> Stopping $svc (decision-path dependency -- must fail CLOSED per FAILURE_MODES.md)"
  stop_service "$svc"
  assert_status "gateway chat fails closed with $svc down" "$(chat_status)" '^(502|500)$'
  if [[ "$svc" == "policy-engine" ]]; then
    assert_status "agent-gate evaluate fails closed with policy-engine down" "$(evaluate_status)" '^(502|500)$'
  fi
  restore_stopped
  assert_status "gateway chat recovers once $svc is back" "$(chat_status)" '^200$'
done

echo "==> Stopping audit (telemetry-only -- must fail OPEN per FAILURE_MODES.md)"
stop_service "audit"
assert_status "gateway chat still succeeds with audit down (fail-open)" "$(chat_status)" '^200$'
restore_stopped
assert_status "gateway chat still succeeds once audit is back" "$(chat_status)" '^200$'

if [[ "$FAILURES" -gt 0 ]]; then
  echo "==> $FAILURES chaos scenario(s) failed -- see FAIL lines above"
  exit 1
fi
echo "==> All chaos scenarios passed -- FAILURE_MODES.md's documented fail-closed/fail-open contract holds"
