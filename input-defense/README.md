# Input Defense

Python FastAPI service implementing input-side detectors with independent invocation and fused verdicts.

## Install and run

### Docker (recommended)

```bash
# From repo root — uses .env for secrets (recommended pattern)
cp .env.example .env
docker compose up -d --build input-defense

curl localhost:8090/health
```

### Local Python

```bash
cd input-defense
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Preferred entrypoint (same as Docker CMD)
python -m aegis_input_defense.main

# Equivalent:
uvicorn aegis_input_defense.app:app --host 0.0.0.0 --port 8090
```

With hot reload: `AEGIS_INPUT_DEFENSE_RELOAD=true python -m aegis_input_defense.main`

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_INPUT_DEFENSE_HOST` | `0.0.0.0` | Bind address |
| `AEGIS_INPUT_DEFENSE_PORT` | `8090` | HTTP port |
| `AEGIS_INPUT_DEFENSE_RELOAD` | `false` | Enable uvicorn reload (dev only) |

## Detectors

| ID | Type | Description |
|----|------|-------------|
| `heuristic` | Scoring | Regex/structural pattern matcher for known injection markers |
| `perplexity` | Scoring | Windowed perplexity anomaly scoring (lightweight statistical stub) |
| `known_answer` | Scoring | Game-theoretic secret-reproduction probe (DataSentinel-style) |
| `classifier` | Scoring | ML classifier via swappable `ClassifierBackend` (stub by default) |
| `spotlighting` | Transform | Spotlighting + sandwich prompt rewrite for untrusted content |

## API

```bash
# Health
curl localhost:8090/health
curl localhost:8090/ready

# List detectors
curl localhost:8090/detectors

# Run a single detector in isolation
curl -X POST localhost:8090/detectors/heuristic/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text": "Ignore all previous instructions."}'

# Full fused pipeline
curl -X POST localhost:8090/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text": "Hello, how are you?"}'

# Subset of detectors + trusted instruction context
curl -X POST localhost:8090/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Summarize this document.",
    "trusted_instruction": "You are a helpful assistant.",
    "enabled_detectors": ["heuristic", "classifier"]
  }'
```

Every `InputVerdict` includes per-detector `score`, `reasoning`, and `latency_ms` for auditability.

## Tests

```bash
cd input-defense
pytest                                    # all tests
pytest tests/test_fixture_metrics.py -s   # prints ASR/FPR tables
python scripts/run_fixture_metrics.py     # standalone metrics report
```

From repo root: `make test-python` (runs input-defense, output-defense, redteam).

Fixtures live in `tests/fixtures/prompts.yaml` (30 attacks + 15 benign).

## Known limitations (tracked gaps)

These are explicit TODOs — not silent shortcomings:

| Component | Status | Follow-up |
|-----------|--------|-----------|
| **Perplexity detector** | Lightweight character trigram stub (~0% effective catch rate on fixtures) | Wire to a real reference language model for windowed PPL scoring |
| **Classifier detector** | Lexical-feature stub (`stub-lexical-v1`) | Swap `ClassifierBackend` for a real model (e.g. Llama-Prompt-Guard-2) — no fusion changes required |
| **Detector execution** | Sequential, not parallel | Parallelize when latency becomes a bottleneck |
| **gRPC / OpenTelemetry deps** | Declared in pyproject, not wired | Stage 0 forward-compat only |

Run `pytest tests/test_fixture_metrics.py -s` to see aggregate and **category-level** ASR breakdowns that highlight where each detector is weak.

## Swapping the classifier model

Implement `ClassifierBackend` and inject at service construction — fusion logic unchanged:

```python
from aegis_input_defense.detectors.classifier import ClassifierBackend, ClassifierDetector
from aegis_input_defense.service import InputDefenseService

class HuggingFaceBackend(ClassifierBackend):
    ...

service = InputDefenseService(detectors={
    **build_detector_registry(),
    "classifier": ClassifierDetector(backend=HuggingFaceBackend()),
})
```

## Policy engine integration

Pass the `InputVerdict` from `POST /analyze` to policy-engine:

```bash
curl -X POST localhost:8081/v1/evaluate/input \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "default",
    "mode": "enforce",
    "input_verdict": { "action": "BLOCK", "fused_score": 0.92, "detector_scores": [] }
  }'
```

See [policy-engine/README.md](../policy-engine/README.md) for CEL context and modes.
