#!/usr/bin/env bash
# Real-ML-backend load test. NOT run in CI -- CI deliberately disables ML
# backends for speed (see .github/workflows/ci.yml's env block), and this
# sandbox/this script's authoring environment has no Docker daemon to run
# the ML overlay against, so unlike scripts/benchmark.sh, the numbers this
# produces have never been observed by the author. Run this yourself
# against a box that actually has docker-compose.demo-ml.yml up (an
# A1.Flex Oracle box, or a beefy enough local machine -- see that
# overlay's own comments for the ~2GB/~1.5GB RAM budget) and report back
# the real p50/p95/p99 numbers so they can be written up properly
# (RESULTS.md is about defensive-capability/ASR results specifically;
# this would want its own writeup once real numbers exist).
#
# Tests three targets separately so each defense layer's real inference
# cost is visible on its own, not just blended into one end-to-end
# number: input-defense and output-defense directly (bypassing the
# gateway, isolating each detector's real latency), then the full
# gateway pipeline (the number that actually matters to a real caller).
#
# Rate/duration default low and short on purpose -- real ML inference is
# much slower than the stub backends scripts/benchmark.sh tests, and this
# is meant to be a careful first look at real numbers, not a stress test.
# Override with LOAD_TEST_ML_RATE / LOAD_TEST_ML_DURATION once you know
# what the box can actually take.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="${ROOT}/benchmark-results"
mkdir -p "$RESULTS_DIR"

# Local dev convenience: same .env auto-source as scripts/integration and
# scripts/benchmark.sh -- this script is manual-only (never run by CI), so
# there is no throwaway-CI-credential case to worry about being a no-op for.
if [[ -f "$ROOT/.env" && ( -z "${AEGIS_API_KEYS:-}" || -z "${AEGIS_INTERNAL_TOKEN:-}" ) ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

INPUT_DEFENSE_URL="${INPUT_DEFENSE_URL:-http://localhost:8090}"
OUTPUT_DEFENSE_URL="${OUTPUT_DEFENSE_URL:-http://localhost:8091}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
DURATION="${LOAD_TEST_ML_DURATION:-30s}"
RATE="${LOAD_TEST_ML_RATE:-2/s}"

if ! command -v vegeta >/dev/null 2>&1; then
  echo "ERROR: vegeta is not installed. https://github.com/tsenart/vegeta" >&2
  exit 1
fi
if [ -z "${AEGIS_INTERNAL_TOKEN:-}" ]; then
  echo "ERROR: AEGIS_INTERNAL_TOKEN must be set -- input-defense/output-defense" >&2
  echo "       reject unauthenticated requests now (Stage A.1)." >&2
  exit 1
fi
if [ -z "${AEGIS_API_KEYS:-}" ]; then
  echo "ERROR: AEGIS_API_KEYS must be set for the gateway target." >&2
  exit 1
fi
API_KEY="${AEGIS_API_KEYS%%,*}"

run_attack() {
  local name="$1" url="$2" body_file="$3" auth_header="$4"
  local results_bin="${RESULTS_DIR}/ml-${name}.bin"
  echo
  echo "==> Load-testing ${name} at ${url} (rate=${RATE}, duration=${DURATION})"
  echo "POST ${url}" | vegeta attack \
    -duration="$DURATION" \
    -rate="$RATE" \
    -header "$auth_header" \
    -header "Content-Type: application/json" \
    -body="$body_file" \
    > "$results_bin"
  vegeta report -type=text "$results_bin"
  vegeta report -type=json "$results_bin" > "${RESULTS_DIR}/ml-${name}.json"
  echo "==> Wrote ${RESULTS_DIR}/ml-${name}.json"
}

INPUT_BODY="$(mktemp)"
OUTPUT_BODY="$(mktemp)"
GATEWAY_BODY="$(mktemp)"
trap 'rm -f "$INPUT_BODY" "$OUTPUT_BODY" "$GATEWAY_BODY"' EXIT

cat > "$INPUT_BODY" << 'JSON'
{"tenant_id":"load-test","trace":{"trace_id":"load-test","request_id":"load-test"},"text":"What is the capital of France, and can you also recommend a good bakery there?"}
JSON

cat > "$OUTPUT_BODY" << 'JSON'
{"tenant_id":"load-test","trace":{"trace_id":"load-test","request_id":"load-test"},"content":"The capital of France is Paris. For a good bakery, I'd recommend Poilane in the 6th arrondissement.","original_prompt":"What is the capital of France, and can you also recommend a good bakery there?"}
JSON

cat > "$GATEWAY_BODY" << 'JSON'
{"model":"mock-model","messages":[{"role":"user","content":"What is the capital of France?"}]}
JSON

run_attack "input-defense"  "${INPUT_DEFENSE_URL}/analyze"           "$INPUT_BODY"   "Authorization: Bearer ${AEGIS_INTERNAL_TOKEN}"
run_attack "output-defense" "${OUTPUT_DEFENSE_URL}/analyze"          "$OUTPUT_BODY"  "Authorization: Bearer ${AEGIS_INTERNAL_TOKEN}"
run_attack "gateway"        "${GATEWAY_URL}/v1/chat/completions"     "$GATEWAY_BODY" "Authorization: Bearer ${API_KEY}"

echo
echo "==> Real-ML-backend load test complete. Results in ${RESULTS_DIR}/ml-*.json"
echo "    These numbers have never been observed before -- please report them back"
echo "    so they can be written up (RESULTS.md is ASR-specific, this needs its own doc)."
