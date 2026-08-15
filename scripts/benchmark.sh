#!/usr/bin/env bash
# Load-testing harness for the gateway's defended chat-completion pipeline
# (input-defense -> policy -> model-router -> output-defense -> policy).
#
# This is the CI-safe profile: short duration, modest rate, run against
# whatever backends the caller already has running (CI runs it with the
# stub/mock detector backends -- see .github/workflows/ci.yml's "Start
# stack" step -- since real ML backends are deliberately disabled there
# for speed). It measures the pipeline's own overhead (auth, defense
# calls, policy evaluation, JSON marshaling) under load, not real-model
# inference latency.
#
# For real-ML-backend load testing (Toxic-BERT, DeBERTa, spaCy NER under
# docker-compose.demo-ml.yml), use scripts/load-test-ml.sh instead --
# deliberately a separate script, not run in CI, since CI never has that
# overlay up.
#
# IMPORTANT, TRACKED FOR FUTURE WORK: this script is informational only.
# It reports latency/throughput/error-rate but does not gate CI on any
# threshold, because there is no real baseline yet to set a sane
# threshold against. Revisit this once a few real runs establish what
# "normal" looks like for this pipeline -- see the project's own
# tracking of this decision (asked and explicitly deferred by the
# operator when Stage D.1 was scoped). The one thing this script DOES
# still fail on is the harness itself not working at all (vegeta
# missing, or literally zero successful requests) -- that's a broken
# test, not a slow service, and should never pass silently.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="${ROOT}/benchmark-results"
mkdir -p "$RESULTS_DIR"

# Local dev convenience: pick up the same credentials used to start the
# stack from .env if they aren't already in the environment -- same
# pattern as scripts/integration. CI sets AEGIS_API_KEYS explicitly (no
# .env file exists in a fresh CI checkout), so this is a no-op there.
if [[ -f "$ROOT/.env" && -z "${AEGIS_API_KEYS:-}" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
DURATION="${BENCHMARK_DURATION:-20s}"
RATE="${BENCHMARK_RATE:-10/s}"

if ! command -v vegeta >/dev/null 2>&1; then
  echo "ERROR: vegeta is not installed. Install it (a single static binary,"   >&2
  echo "       no other dependencies): https://github.com/tsenart/vegeta"      >&2
  echo "       or 'go install github.com/tsenart/vegeta/v12@latest'."          >&2
  exit 1
fi

API_KEY="${AEGIS_API_KEYS%%,*}"
if [ -z "$API_KEY" ]; then
  echo "ERROR: AEGIS_API_KEYS must be set (the gateway's own auth -- see"     >&2
  echo "       scripts/generate-credentials.sh, or CI's throwaway test key)." >&2
  exit 1
fi

BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
cat > "$BODY_FILE" << 'JSON'
{"model":"mock-model","messages":[{"role":"user","content":"What is the capital of France?"}]}
JSON

RESULTS_BIN="${RESULTS_DIR}/gateway-chat.bin"
echo "==> Load-testing ${GATEWAY_URL}/v1/chat/completions (rate=${RATE}, duration=${DURATION})"
echo "POST ${GATEWAY_URL}/v1/chat/completions" | vegeta attack \
  -duration="$DURATION" \
  -rate="$RATE" \
  -header "Authorization: Bearer ${API_KEY}" \
  -header "Content-Type: application/json" \
  -body="$BODY_FILE" \
  > "$RESULTS_BIN"

vegeta report -type=text "$RESULTS_BIN"
vegeta report -type=json "$RESULTS_BIN" > "${RESULTS_DIR}/gateway-chat.json"

SUCCESS_RATIO="$(jq -r '.success' "${RESULTS_DIR}/gateway-chat.json")"
REQUESTS="$(jq -r '.requests' "${RESULTS_DIR}/gateway-chat.json")"
echo "==> Wrote ${RESULTS_DIR}/gateway-chat.json (requests=${REQUESTS}, success_ratio=${SUCCESS_RATIO})"

# Informational only (see the header comment) -- but a harness that ran
# zero successful requests measured nothing, and shouldn't report success.
# jq (already a hard dependency here) does the numeric comparison, not
# bc -- bc isn't guaranteed present on every box this might run on
# (notably recent macOS), a real portability lesson from earlier in this
# same project.
ALL_FAILED="$(jq -r 'if .requests > 0 and .success == 0 then "true" else "false" end' "${RESULTS_DIR}/gateway-chat.json")"
if [ "$REQUESTS" -eq 0 ] || [ "$ALL_FAILED" = "true" ]; then
  echo "ERROR: 0 successful requests -- the load-test harness itself is broken" >&2
  echo "       (not a slow-service finding). Check that the gateway is up and" >&2
  echo "       reachable at ${GATEWAY_URL} with a valid AEGIS_API_KEYS." >&2
  exit 1
fi

echo "==> Benchmark complete (informational only -- no CI gate on these numbers yet)."
