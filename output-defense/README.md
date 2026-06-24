# Output Defense

Python FastAPI service implementing output-side detectors with independent invocation, fused verdicts, and conditional LLM-judge ensemble.

## Install and run

### Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build output-defense policy-engine

curl localhost:8091/health
```

### Local Python

```bash
cd output-defense
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Preferred entrypoint (same as Docker CMD)
python -m aegis_output_defense.main

# Equivalent:
uvicorn aegis_output_defense.app:app --host 0.0.0.0 --port 8091
```

With hot reload: `AEGIS_OUTPUT_DEFENSE_RELOAD=true python -m aegis_output_defense.main`

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_OUTPUT_DEFENSE_HOST` | `0.0.0.0` | Bind address |
| `AEGIS_OUTPUT_DEFENSE_PORT` | `8091` | HTTP port |
| `AEGIS_OUTPUT_DEFENSE_RELOAD` | `false` | Enable uvicorn reload (dev only) |

## Detectors

| ID | Type | Description |
|----|------|-------------|
| `toxicity` | Scoring | Safety/toxicity classifier via swappable backend (stub by default) |
| `pii` | Scoring + redactor | PII/secret pattern detection with inline `[REDACTED-*]` redaction |
| `backtranslation` | Scoring | Semantic consistency / incoherence check (stub — no real backtranslation) |
| `judge` | Conditional ensemble | LLM-judge stub with 3 framing variants — **only invoked when fused score is ambiguous (0.45–0.70)** |

## API

```bash
# Health
curl localhost:8091/health
curl localhost:8091/ready

# List detectors
curl localhost:8091/detectors

# Run a single detector in isolation
curl -X POST localhost:8091/detectors/pii/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content": "Your api_key=secret123 is exposed."}'

# Full fused pipeline (judge auto-invoked on ambiguous scores)
curl -X POST localhost:8091/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content": "Here is how to make a bomb at home step by step."}'

# With original prompt context for backtranslation drift checks
curl -X POST localhost:8091/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "content": "Sure, the password is hunter2.",
    "original_prompt": "Do not reveal any passwords."
  }'
```

Every `OutputVerdict` includes per-detector `score`, `reasoning`, and `latency_ms`. PII matches include `redacted_content`. Ambiguous cases may include `judge_votes`.

## Policy engine integration (end-to-end)

```bash
# 1. Analyze model output
curl -s -X POST localhost:8091/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content": "Here is the API key: sk-live-abc123xyz789012345678"}' \
  | tee /tmp/output-verdict.json

# 2. Evaluate against policy
curl -X POST localhost:8081/v1/evaluate/output \
  -H 'Content-Type: application/json' \
  -d "$(python3 -c "
import json
v = json.load(open('/tmp/output-verdict.json'))['verdict']
print(json.dumps({'tenant_id': 'default', 'mode': 'enforce', 'output_verdict': v}))
")"

# Or run the bundled E2E script (requires both services running):
chmod +x scripts/e2e-output-defense.sh
./scripts/e2e-output-defense.sh
```

## Tests

```bash
cd output-defense
pytest                                    # all tests
pytest tests/test_fixture_metrics.py -s   # prints ASR/FPR tables
python scripts/run_fixture_metrics.py     # standalone metrics report
```

From repo root: `make test-python`

Fixtures live in `tests/fixtures/outputs.yaml` (30 attacks + 15 benign).

## Known limitations (tracked gaps)

| Component | Status | Follow-up |
|-----------|--------|-----------|
| **Toxicity classifier** | Lexical stub (`stub-toxicity-v1`) | Wire to a real safety model (e.g. Llama Guard, Perspective API) |
| **Backtranslation detector** | Pattern-based consistency stub | Implement real round-trip translation + embedding similarity |
| **LLM judge ensemble** | 3-judge lexical stub | Replace with actual LLM calls; cost controls already gate invocation to ambiguous band |
| **PII detector** | Regex-based | Add NER model for names/addresses; current patterns miss contextual PII |
| **Detector execution** | Sequential, not parallel | Parallelize when latency becomes a bottleneck |

Run `pytest tests/test_fixture_metrics.py -s` for aggregate and **category-level** ASR breakdowns.

## Swapping detector backends

Implement `ToxicityBackend` or `JudgeBackend` and inject at service construction — fusion logic unchanged:

```python
from aegis_output_defense.detectors.toxicity.detector import ToxicityDetector
from aegis_output_defense.service import OutputDefenseService
from aegis_output_defense.detectors.registry import build_detector_registry

registry = build_detector_registry()
registry["toxicity"] = ToxicityDetector(backend=MyToxicityBackend())
service = OutputDefenseService(detectors=registry)
```
