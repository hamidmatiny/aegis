#!/usr/bin/env bash
set -euo pipefail

# Stage 0 benchmark harness placeholder.
# Expanded in later stages to measure ASR and p50/p95/p99 latency overhead.

echo "==> AEGIS benchmark harness (Stage 0 scaffold)"
echo "    Full ASR/latency benchmarks activate after defense layers are implemented."
echo '{"stage": 0, "status": "scaffold", "asr": null, "latency_ms": null}' > benchmark-results/stage0.json
echo "==> Wrote benchmark-results/stage0.json"
