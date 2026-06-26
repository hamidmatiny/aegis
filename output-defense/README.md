# Output Defense

Python FastAPI service implementing output-side detectors with independent invocation, fused verdicts, and conditional LLM-judge ensemble.

**Phase H2 (production hardening):** toxicity, PII, backtranslation, and judge detectors now run real models by default (see [Before/after metrics](#h2-beforeafter-fixture-metrics)).

## Install and run

### Docker (recommended)

```bash
# From repo root — uses .env for secrets (recommended pattern)
cp .env.example .env
docker compose up -d --build output-defense policy-engine model-router

curl localhost:8091/health
curl localhost:8091/ready   # warms local ML models when enabled
```

`docker compose` defaults to **stub/regex** backends so CI and local stacks start without downloading weights or calling model-router. For real models:

```bash
AEGIS_OUTPUT_DEFENSE_INSTALL_ML=true \
AEGIS_OUTPUT_DEFENSE_TOXICITY_BACKEND=toxic-bert \
AEGIS_OUTPUT_DEFENSE_PII_BACKEND=ner \
AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_BACKEND=router \
AEGIS_OUTPUT_DEFENSE_JUDGE_BACKEND=router \
docker compose up -d --build output-defense model-router
```

| Variable | Docker default | Purpose |
|----------|----------------|---------|
| `AEGIS_OUTPUT_DEFENSE_INSTALL_ML` | `false` | When `true`, image installs `.[ml]` + spaCy `en_core_web_sm` |
| `AEGIS_OUTPUT_DEFENSE_TOXICITY_BACKEND` | `stub` | `toxic-bert` for Toxic-BERT + harm lexicon |
| `AEGIS_OUTPUT_DEFENSE_PII_BACKEND` | `regex` | `ner` for regex first-pass + spaCy NER second-pass |
| `AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_BACKEND` | `router` | `router` for model-router restatement divergence |
| `AEGIS_OUTPUT_DEFENSE_JUDGE_BACKEND` | `stub` | `router` for 3-judge LLM ensemble on ambiguous scores |
| `AEGIS_MODEL_ROUTER_URL` | `http://model-router:8082` | Required when router backends are enabled |
| `AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_PROVIDER` | `grok` | model-router provider id for restatement |
| `AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_MODEL` | `grok-4.3` | Model id passed with `provider` to model-router |
| `AEGIS_OUTPUT_DEFENSE_JUDGE_PROVIDER` | `grok` | model-router provider id for judge ensemble |
| `AEGIS_OUTPUT_DEFENSE_JUDGE_MODEL` | `grok-4.3` | Model id for judge calls |
| `AEGIS_OUTPUT_DEFENSE_ROUTER_TIMEOUT` | `60.0` | model-router HTTP timeout (seconds) |
| `AEGIS_OUTPUT_DEFENSE_ROUTER_MAX_RETRIES` | `3` | Retries on 429/5xx/timeout before surfacing error |
| `AEGIS_OUTPUT_DEFENSE_ROUTER_RETRY_BACKOFF_SECONDS` | `1.0` | Exponential backoff base between retries |
| `AEGIS_AUDIT_EMIT` | `true` | Toggle audit emission |

### Local Python

```bash
cd output-defense
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[ml,dev]'
python -m spacy download en_core_web_sm

# Preferred entrypoint (same as Docker CMD)
python -m aegis_output_defense.main

# Equivalent:
uvicorn aegis_output_defense.app:app --host 0.0.0.0 --port 8091
```

With hot reload: `AEGIS_OUTPUT_DEFENSE_RELOAD=true python -m aegis_output_defense.main`

**First run:** Hugging Face downloads ~440 MB (Toxic-BERT) plus ~12 MB spaCy model. Subsequent starts reuse cache.

### Stub mode (fast CI / no ML downloads)

```bash
AEGIS_OUTPUT_DEFENSE_TOXICITY_BACKEND=stub \
AEGIS_OUTPUT_DEFENSE_PII_BACKEND=regex \
AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_BACKEND=stub \
AEGIS_OUTPUT_DEFENSE_JUDGE_BACKEND=stub \
pytest
```

Pytest uses stub backends by default (`tests/conftest.py`).

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_OUTPUT_DEFENSE_HOST` | `0.0.0.0` | Bind address |
| `AEGIS_OUTPUT_DEFENSE_PORT` | `8091` | HTTP port |
| `AEGIS_OUTPUT_DEFENSE_RELOAD` | `false` | Enable uvicorn reload (dev only) |
| `AEGIS_OUTPUT_DEFENSE_TOXICITY_BACKEND` | `toxic-bert` | `toxic-bert` or `stub` |
| `AEGIS_OUTPUT_DEFENSE_PII_BACKEND` | `ner` | `ner` (regex+spaCy) or `regex` |
| `AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_BACKEND` | `router` | `router` or `stub` |
| `AEGIS_OUTPUT_DEFENSE_JUDGE_BACKEND` | `router` | `router` or `stub` |
| `AEGIS_OUTPUT_DEFENSE_TOXIC_BERT_MODEL_ID` | `unitary/toxic-bert` | Hugging Face toxicity model |
| `AEGIS_OUTPUT_DEFENSE_SPACY_MODEL` | `en_core_web_sm` | spaCy NER model for PII pass |
| `AEGIS_MODEL_ROUTER_URL` | `http://localhost:8082` | model-router base URL |
| `AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_MODEL` | `mock-model` | Router model for restatement |
| `AEGIS_OUTPUT_DEFENSE_JUDGE_MODEL` | `mock-model` | Router model for judge calls |
| `AEGIS_OUTPUT_DEFENSE_ROUTER_TIMEOUT` | `60.0` | model-router HTTP timeout (seconds) |
| `AEGIS_OUTPUT_DEFENSE_ROUTER_MAX_RETRIES` | `3` | Retries on 429/5xx/timeout before surfacing error |
| `AEGIS_OUTPUT_DEFENSE_ROUTER_RETRY_BACKOFF_SECONDS` | `1.0` | Exponential backoff base between retries |
| `AEGIS_AUDIT_URL` | `""` | Audit service |
| `AEGIS_AUDIT_EMIT` | `true` | Emit signed receipts |

## Detectors

| ID | Type | H2 backend | Description |
|----|------|------------|-------------|
| `toxicity` | Scoring | Toxic-BERT + harm lexicon | Multi-label comment toxicity + Phase 1 weapon/malware patterns |
| `pii` | Scoring + redactor | Regex + spaCy NER | Credentials via regex; names/locations via context-gated NER |
| `backtranslation` | Scoring | model-router restatement | LLM restates intent; divergence score flags semantic smoothing |
| `judge` | Conditional ensemble | 3× model-router judges | Only on ambiguous fused band (0.45–0.70); majority vote |

### Model choices (H2)

| Component | Model | Why |
|-----------|-------|-----|
| Toxicity | `unitary/toxic-bert` (~110M, ungated) | Strong on hate/harassment; paired with harm lexicon for weapon/malware recall |
| PII NER | spaCy `en_core_web_sm` | Lightweight local NER; context-gated to avoid benign name FPR |
| Backtranslation / judge | model-router (Grok via existing wiring) | Reuses Stage 4 router — no new direct API dependency |

### Obfuscation normalization (decode-and-rescan)

Before scoring, `analyze` expands the scan surface for each detector:

1. **Zero-width strip** — removes smuggled Unicode separators
2. **Base64 decode-and-rescan** — decodes embedded blobs and re-runs detectors on plaintext

Each detector runs on every surface; the **max score** is used for fusion.

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

# Or run the bundled E2E script (requires services running):
chmod +x scripts/e2e-output-defense.sh
./scripts/e2e-output-defense.sh
```

## Tests

```bash
cd output-defense
pytest                                    # all tests (stub backends)
pytest tests/test_fixture_metrics.py -s   # prints ASR/FPR tables
pytest tests/test_ml_backends.py -s       # real-model smoke (requires .[ml])

# Phase 1 stub baseline
python scripts/run_fixture_metrics.py --toxicity-backend stub --pii-backend regex --backtranslation-backend stub

# H2 real local backends (router backends still stub in this script)
python scripts/run_fixture_metrics.py --toxicity-backend toxic-bert --pii-backend ner --warmup

# Ablation study (H3)
python scripts/run_ablation_study.py --toxicity-backend stub --pii-backend regex --backtranslation-backend stub
python scripts/run_ablation_study.py --toxicity-backend toxic-bert --pii-backend ner --warmup
```

From repo root: `make test-python`

Fixtures live in `tests/fixtures/outputs.yaml` (30 attacks + 15 benign).

## H2 before/after fixture metrics

Threshold **0.50**, `invoke_judge=False` (same as Phase 1 regression suite).

**Important:** The original H2 report used `run_fixture_metrics.py` with `--backtranslation-backend stub` (the script default) and **model-router was not running**. Backtranslation/judge router paths were never exercised in that comparison.

| Detector | Phase 1 stub ASR | Phase 1 stub FPR | H2 local ML ASR | H2 local ML FPR |
|----------|------------------|------------------|-----------------|-------------|
| toxicity | 33.3% | 0.0% | 33.3% | 0.0% |
| pii | 26.7% | 0.0% | 26.7% | 0.0% |
| backtranslation | 33.3% | 0.0% | 33.3% (stub path) | 0.0% |
| fused | 86.7% | 0.0% | 86.7% | 0.0% |

Run with **backend execution audit** (shows requested vs actual path per detector):

```bash
python scripts/run_fixture_metrics.py --toxicity-backend toxic-bert --pii-backend ner --warmup
python scripts/run_fixture_metrics.py --backtranslation-backend router   # needs model-router up
```

**Harness behaviour:** `run_fixture_metrics.py` scores each fixture **once** via `analyze_all` (45 router calls when backtranslation=router, not ~165 redundant calls). Per-fixture progress prints to **stderr** immediately (`[1/45] ben-helpful-001 (benign) 3.2s`). Router HTTP uses connect/read/write timeouts (60s read default) with 3× retry on 429/5xx.

### Why local ML ASR matches stub on this fixture set

| Detector | Root cause (not a silent fallback bug) |
|----------|----------------------------------------|
| **Toxicity** | `ToxicBERTBackend` runs real inference but uses `max(ml_score, lexical_score)` where lexical uses the **same patterns as the stub**. All 10 stub catches are lexical-dominated; ML scores differ on 4 fixtures but **none cross the 0.50 threshold differently**. Audit shows `toxic-bert-lexical-calibration` on 37/45 fixtures and `toxic-bert-ml` on 8/45. |
| **PII** | All 8 `leaked_pii` attacks are caught by **regex alone** (100% category ASR). Context-gated NER adds **0 threshold outcome changes** on this set — audit reports `NER changed threshold outcome on 0 fixtures`. |
| **Backtranslation** | With `mock-model`, router returns `[mock:…]` echoes → **100% stub-fallback-mock-echo** (identical pattern scores). Real divergence scoring requires a non-mock LLM restatement (Grok/OpenAI via model-router + API key). |

The fixture set is now **too coarse** to show ML/NER/router improvements at aggregate ASR — it needs harder examples (paraphrased toxicity, name-only PII leaks without credential patterns, semantic smoothing jailbreaks). Tracked for H3 adaptive campaigns.

**By category (fused ASR, local ML backends, backtranslation=stub):**

| Category | Phase 1 stub | H2 real |
|----------|--------------|---------|
| leaked PII/secrets | 100% | 100% |
| toxic/harmful | 88% | 88% |
| jailbreak success | 100% | 100% |
| hallucination/incoherent | 57% | 57% |

With `--backtranslation-backend router` and model-router on **mock-model**, audit shows `stub-fallback-mock-echo: 45/45` — router HTTP calls occur (~1.6s for 45 fixtures) but scores match the pattern stub.

### Router-live backtranslation (Grok) — calibration

First Grok run **before recalibration** (meta-analytic restate prompt + raw Jaccard drift):

| Metric | stub | Grok router-live (pre-calibration) |
|--------|------|-------------------------------------|
| backtranslation ASR | 33.3% | 83.3% |
| backtranslation FPR | 0.0% | **73.3%** (11/15 benign) |

**Root cause:** The restate prompt asked Grok to *describe* the text ("The text states…") rather than paraphrase it. Raw Jaccard token overlap treats that meta-analytic rewrite as high drift even when meaning is identical — conflating *different wording* with *different meaning*.

**Recalibration (current):** Direct-paraphrase prompt + content-recall similarity + **code identifier recall** (function/param names for `def`/`class`/import snippets), synonym-aware matching, meta-framing strip, policy-refusal drift cap, and harm-sensitive omission boost (skipped on refusals). Post-calibration Grok run (**agent session**, 2026-06-25, `--toxicity-backend stub --pii-backend regex`): backtranslation FPR **6.7%** (1/15). **Your terminal run** (2026-06-26, default toxic-bert/ner backends): backtranslation FPR **13.3%** (2/15), fused FPR **6.7%** (1/15) — see your `run_fixture_metrics.py` aggregate table for exact numbers; Grok restatements vary between runs.

Re-run after adding bare-code fixtures (`ben-code-003`–`005`, 48 fixtures total):

```bash
python scripts/run_fixture_metrics.py \
  --backtranslation-backend router \
  --backtranslation-provider grok --backtranslation-model grok-4.3
```

Label whether numbers come from your run or an agent session when comparing.

**Mock-echo fallback (1/45):** `atk-toxic-007` (CSAM-adjacent). Not a timeout or rate limit — Grok and all real providers in the fallback chain **refused** the restate request; model-router exhausted the chain and returned mock echo (`attempted_providers: grok, openai, anthropic, ollama, mock`). Output-defense correctly falls back to pattern stub for that fixture.

**Router client retries:** `ModelRouterClient` retries transient 429/5xx/timeout errors (3×, exponential backoff) before surfacing failure — important for H3 adaptive campaigns.

## Model footprint and latency

| Asset | Size (approx.) | Notes |
|-------|----------------|-------|
| Toxic-BERT | ~440 MB | Hugging Face cache |
| spaCy `en_core_web_sm` | ~12 MB | `python -m spacy download en_core_web_sm` |
| Cold `/ready` warmup | ~2.8 s | CPU, first load |
| Toxicity inference p50 | ~40 ms | After warmup |
| PII (regex+NER) p50 | ~4 ms | After spaCy loaded |

## Router cost / latency (backtranslation + judge)

These detectors make **real model-router HTTP calls** when `*_BACKEND=router`:

| Call | When | Typical cost |
|------|------|--------------|
| Backtranslation restatement | Every fused analyze (always-on detector) | 1× chat completion per analyze |
| Judge ensemble | Fused score in ambiguous band (0.45–0.70) only | Up to 3× chat completions |

With `mock-model` (default in compose), router returns deterministic echoes and backends fall back to pattern logic. Point `AEGIS_OUTPUT_DEFENSE_*_MODEL` at a real provider model (e.g. Grok via model-router config) for production semantic checks.

**Example judge latency:** 3 sequential router calls × provider RTT (typically 1–5 s each with real LLM).

## Known limitations (tracked gaps)

| Component | Status | Follow-up |
|-----------|--------|-----------|
| **Toxicity** | Toxic-BERT + lexicon | Llama Guard when ungated local weights are practical |
| **PII NER** | spaCy sm + context gate | Presidio or larger NER for addresses/IBAN |
| **Backtranslation** | Router restatement + recall/identifier-weighted divergence | Grok restatement variance; vague code paraphrases that omit identifiers may still score ambiguous |
| **Judge** | 3× router SAFE/UNSAFE vote | Structured JSON schema parsing; parallel judge calls |
| **Detector execution** | Sequential | Parallelize when latency becomes a bottleneck |

## Swapping detector backends

Implement `ToxicityBackend`, `BacktranslationBackend`, or `JudgeBackend` and inject via registry — fusion logic unchanged:

```python
from aegis_output_defense.detectors.registry import build_detector_registry
from aegis_output_defense.service import OutputDefenseService

registry = build_detector_registry(toxicity_backend="stub")
service = OutputDefenseService(detectors=registry)
```
