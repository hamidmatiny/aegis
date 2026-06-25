# Input Defense

Python FastAPI service implementing input-side detectors with independent invocation and fused verdicts.

**Phase H1 (production hardening):** classifier and perplexity detectors now run real local ML models by default (see [Before/after metrics](#h1-beforeafter-fixture-metrics)).

## Install and run

### Docker (recommended)

```bash
# From repo root — uses .env for secrets (recommended pattern)
cp .env.example .env
docker compose up -d --build input-defense

curl localhost:8090/health
curl localhost:8090/ready   # warms ML models on first call (~4s cold load)
```

Docker installs the `[ml]` optional dependencies and downloads models on first `/ready` or `/analyze` request.

### Local Python

```bash
cd input-defense
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[ml,dev]'

# Preferred entrypoint (same as Docker CMD)
python -m aegis_input_defense.main

# Equivalent:
uvicorn aegis_input_defense.app:app --host 0.0.0.0 --port 8090
```

With hot reload: `AEGIS_INPUT_DEFENSE_RELOAD=true python -m aegis_input_defense.main`

**First run:** Hugging Face downloads ~1.0 GB of model weights (see [Model footprint](#model-footprint)). Subsequent starts reuse the local cache.

### Stub mode (fast CI / no ML downloads)

```bash
AEGIS_INPUT_DEFENSE_CLASSIFIER_BACKEND=stub \
AEGIS_INPUT_DEFENSE_PERPLEXITY_BACKEND=stub \
python -m aegis_input_defense.main
```

Pytest uses stub backends by default (`tests/conftest.py`).

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_INPUT_DEFENSE_HOST` | `0.0.0.0` | Bind address |
| `AEGIS_INPUT_DEFENSE_PORT` | `8090` | HTTP port |
| `AEGIS_INPUT_DEFENSE_RELOAD` | `false` | Enable uvicorn reload (dev only) |
| `AEGIS_INPUT_DEFENSE_CLASSIFIER_BACKEND` | `prompt-guard` | `prompt-guard` (real ML) or `stub` (lexical Phase 1) |
| `AEGIS_INPUT_DEFENSE_PERPLEXITY_BACKEND` | `lm` | `lm` (DistilGPT2) or `stub` (char trigram Phase 1) |
| `AEGIS_INPUT_DEFENSE_PROMPT_GUARD_MODEL_ID` | `protectai/deberta-v3-base-prompt-injection-v2` | Hugging Face sequence-classifier checkpoint |
| `AEGIS_INPUT_DEFENSE_PERPLEXITY_MODEL_ID` | `distilgpt2` | Causal LM for token-level perplexity |
| `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` | _(unset)_ | Required only for **gated** Hugging Face models (see below) |

Audit emission (unchanged): set `AEGIS_AUDIT_URL` / `AEGIS_AUDIT_EMIT` from repo root `.env` when running via compose.

## Detectors

| ID | Type | Backend (H1 default) |
|----|------|----------------------|
| `heuristic` | Scoring | Regex/structural patterns (unchanged) |
| `perplexity` | Scoring | **DistilGPT2** token-level PPL + windowed anomaly |
| `known_answer` | Scoring | Game-theoretic secret probe (unchanged) |
| `classifier` | Scoring | **DeBERTa prompt-injection classifier** via `ClassifierBackend` |
| `spotlighting` | Transform | Spotlighting + sandwich rewrite (unchanged) |

Fusion weights and `InputVerdict` schema are unchanged from Stage 2.

### Classifier model choice

| Model | Params | Access | Notes |
|-------|--------|--------|-------|
| `meta-llama/Llama-Prompt-Guard-2-86M` | ~86M | **Gated** (HF approval + token) | Target model from Phase H1 spec — set `AEGIS_INPUT_DEFENSE_PROMPT_GUARD_MODEL_ID` |
| `protectai/deberta-v3-base-prompt-injection-v2` | ~184M | **Ungated** | **Default** for clone-and-run reproducibility without HF approvals |

We default to Protect AI DeBERTa because Meta's Llama-Prompt-Guard-2-86M (and several Protect AI *small* checkpoints) are Hugging Face gated repos. The backend is model-agnostic — swap via `AEGIS_INPUT_DEFENSE_PROMPT_GUARD_MODEL_ID` with no fusion changes.

```bash
# Example: use Llama Prompt Guard when HF access is granted
export HF_TOKEN=hf_...
export AEGIS_INPUT_DEFENSE_PROMPT_GUARD_MODEL_ID=meta-llama/Llama-Prompt-Guard-2-86M
python -m aegis_input_defense.main
```

### Model footprint

Measured on macOS arm64, CPU inference, first download:

| Artifact | Disk (HF cache) | Cold load | p50 latency / request |
|----------|-----------------|-----------|------------------------|
| Classifier (`protectai/deberta-v3-base-prompt-injection-v2`) | ~714 MB | ~2.5 s | ~40 ms |
| Perplexity LM (`distilgpt2`) | ~339 MB | ~1.3 s | ~21 ms |
| **Total** | **~1.05 GB** | **~3.8 s** | sequential per detector |

Plus PyTorch/transformers install (~500 MB–1 GB depending on platform).

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
pytest                                    # all tests (stub backends)
pytest tests/test_fixture_metrics.py -s   # prints ASR/FPR tables (stub)
pytest tests/test_ml_backends.py -s       # real-model smoke tests (requires .[ml])

# Real-model fixture metrics (downloads models on first run)
python scripts/run_fixture_metrics.py --classifier-backend prompt-guard --perplexity-backend lm --warmup

# Phase 1 stub baseline for comparison
python scripts/run_fixture_metrics.py --classifier-backend stub --perplexity-backend stub
```

From repo root: `make test-python` (runs input-defense among other Python services; uses stub backends).

Fixtures live in `tests/fixtures/prompts.yaml` (30 attacks + 15 benign).

## H1 before/after fixture metrics

Threshold **0.50** (same as Phase 1). ASR = attack catch rate; FPR = benign false-positive rate.

### Aggregate

| Detector | Phase 1 stub ASR | Phase 1 stub FPR | H1 real ASR | H1 real FPR |
|----------|------------------|------------------|-------------|-------------|
| heuristic | 80.0% | 0.0% | 80.0% | 0.0% |
| **perplexity** | **0.0%** | **0.0%** | **53.3%** | **20.0%** |
| known_answer | 66.7% | 0.0% | 66.7% | 0.0% |
| **classifier** | **53.3%** | **0.0%** | **93.3%** | **6.7%** |
| **fused** | **83.3%** | **0.0%** | **96.7%** | **6.7%** |

### ASR by attack category (H1 real models)

| Category | N | heuristic | perplexity | known_answer | classifier | fused |
|----------|---|-----------|------------|--------------|------------|-------|
| direct injection | 7 | 5/7 (71%) | 4/7 (57%) | 5/7 (71%) | 7/7 (100%) | 7/7 (100%) |
| role-play | 7 | 5/7 (71%) | 3/7 (43%) | 1/7 (14%) | 6/7 (86%) | 7/7 (100%) |
| encoding/obfuscation | 6 | 5/6 (83%) | 6/6 (100%) | 4/6 (67%) | 5/6 (83%) | 5/6 (83%) |
| indirect injection | 6 | 5/6 (83%) | 3/6 (50%) | 6/6 (100%) | 6/6 (100%) | 6/6 (100%) |
| multi-turn | 4 | 4/4 (100%) | 0/4 (0%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |

Reproduce: `python scripts/run_fixture_metrics.py --classifier-backend prompt-guard --perplexity-backend lm --warmup`

## Known limitations (tracked gaps)

| Component | Status | Follow-up |
|-----------|--------|-----------|
| **Classifier default model** | Ungated DeBERTa substitute; Llama-Prompt-Guard-2-86M requires HF gated access | Set `AEGIS_INPUT_DEFENSE_PROMPT_GUARD_MODEL_ID` + `HF_TOKEN` when approved |
| **Perplexity detector** | Real LM improves encoding/obfuscation (100% ASR) but weak on multi-turn (0%) and adds ~20% benign FPR | Tune calibration or use domain-specific reference LM |
| **Detector execution** | Sequential, not parallel | Parallelize when latency becomes a bottleneck |
| **gRPC / OpenTelemetry deps** | Declared in pyproject, not wired | Stage 0 forward-compat only |

## Swapping the classifier model

Implement `ClassifierBackend` and inject at service construction — fusion logic unchanged:

```python
from aegis_input_defense.detectors.classifier import ClassifierBackend, ClassifierDetector
from aegis_input_defense.detectors.registry import build_detector_registry
from aegis_input_defense.service import InputDefenseService

class CustomBackend(ClassifierBackend):
    ...

registry = build_detector_registry()
registry["classifier"] = ClassifierDetector(backend=CustomBackend())
service = InputDefenseService(detectors=registry)
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
