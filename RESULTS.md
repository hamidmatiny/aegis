# AEGIS Phase 2 — Defensive Capability Results (Stage H3)

This document summarizes **adaptive red-team evidence** and **detector ablation** findings after Stages H1–H3. Numbers are reproducible via the scripts cited below; runs are labeled **agent session** vs **your terminal** when they differ.

## Executive summary

Phase 2 replaced stub detectors with real models (H1 input-defense, H2 output-defense) and added an **adaptive red-team engine** (H3) that mutates successful bypasses across multiple campaign rounds. Key takeaways:

1. **H1 real models materially improve input catch rate** — fused ASR rises from 83.3% (stub) to **96.7%** (Prompt-Guard + DistilGPT2) on the input fixture set, with classifier ASR jumping from 53.3% → 93.3%.
2. **H2 local ML backends match stub aggregate ASR on the current output fixture set** — the corpus is regex/lexical-dominated; harder H3 red-team attacks and expanded output fixtures are needed to differentiate toxicity/NER/router paths at aggregate level (see [output-defense/README.md](output-defense/README.md)).
3. **Adaptive campaigns** generate new variants from bypasses (rounds 2+) rather than replaying only the static corpus; baseline round 1 still uses fixtures × strategies.
4. **Ablation** shows which detectors contribute marginally to fused ASR/FPR when removed one at a time.

---

## 1. Red-team bypass: Phase 1 stub vs Phase 2 hardened

**Bypass rate (BR)** = fraction of probes where defense returns `ALLOW`/`TRANSFORM` with `fused_score < 0.50` (inverse of defense ASR on the same payloads).

| Campaign | Probes | Bypasses | Bypass rate | Notes |
|----------|--------|----------|-------------|-------|
| Phase 1 stub baseline | 192 | 47 | **24.5%** | 24 attacks × 8 strategies; stored baseline |
| Phase 2 hardened (round 1) | *live* | *live* | *run below* | H1/H2 default backends via Docker |
| Phase 2 adaptive (rounds 2–3) | *live* | *live* | *run below* | Variants from round-*N*−1 bypasses |

**Phase 1 baseline file:** `redteam/src/aegis_redteam/baselines/phase1_stub_bypass.yaml`

**Reproduce Phase 2 comparison (live stack):**

```bash
cp .env.example .env
docker compose up -d --build input-defense output-defense redteam

cd redteam
python scripts/run_before_after.py --rounds 3
python scripts/run_adaptive_campaign.py --rounds 3
```

**Corpus update (H3):** Red-team attack YAML expanded from 24 → **30** attacks (paraphrased toxicity, name-only PII, semantic-smoothing jailbreaks, softer input injections). Phase 1 baseline remains the pre-expansion 24×8 reference; re-record baseline after corpus changes if you need apples-to-apples history.

### Per-target Phase 1 stub baseline

| Target | Probes | Bypasses | BR |
|--------|--------|----------|-----|
| input_defense | 96 | 28 | 29.2% |
| output_defense | 96 | 19 | 19.8% |

---

## 2. Adaptive campaign design

| Round | Behavior |
|-------|----------|
| **1** | All attack fixtures × selected mutation strategies (`identity`, `paraphrase`, `roleplay`, …) |
| **2+** | For each bypass in round *N*−1, apply up to 5 other mutators (`adaptive:paraphrase`, `adaptive:roleplay`, …) to the **successful payload** |

**API:** `POST /v1/campaigns/run-adaptive`

```bash
curl -X POST localhost:8092/v1/campaigns/run-adaptive \
  -H 'Content-Type: application/json' \
  -d '{"rounds": 3, "max_variants_per_bypass": 5, "store_bypasses": true}'
```

**Environment variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_REDTEAM_ADAPTIVE_ROUNDS` | `3` | Default rounds for CLI scripts |
| `AEGIS_REDTEAM_ADAPTIVE_MAX_VARIANTS_PER_BYPASS` | `5` | Cap variants per bypass per round |

---

## 3. Ablation study — input-defense

**Method:** Score all fixtures with fused pipeline, then re-score with each scoring detector omitted via `enabled_detectors` (`heuristic`, `perplexity`, `known_answer`, `classifier`; `spotlighting` always included).

**Script:** `input-defense/scripts/run_ablation_study.py`

### Phase 1 stub backends (agent session, 2026-06-25)

Threshold **0.50**, 45 fixtures (30 attacks, 15 benign).

| Omitted detector | Fused ASR | Fused FPR | Δ ASR vs full | Δ FPR vs full |
|------------------|-----------|-----------|---------------|---------------|
| *(none — full)* | 83.3% | 0.0% | — | — |
| heuristic | 66.7% | 0.0% | **+16.7%** | 0.0% |
| perplexity | 83.3% | 0.0% | 0.0% | 0.0% |
| known_answer | 83.3% | 0.0% | 0.0% | 0.0% |
| classifier | 83.3% | 0.0% | 0.0% | 0.0% |

**Interpretation (stub):** Only **heuristic** shows marginal fused contribution on this fixture set; stub classifier/perplexity add no fused lift (consistent with Phase 1 known gaps).

### H1 real backends (from H1 README, fixture metrics)

| Omitted detector | Fused ASR | Δ ASR vs full (96.7%) |
|------------------|-----------|------------------------|
| *(none — full)* | **96.7%** | — |
| heuristic | ~80% | ~+17% |
| perplexity | lower | contributes on encoding/obfuscation |
| classifier | lower | largest single-detector lift vs stub |

Reproduce real ablation:

```bash
cd input-defense
python scripts/run_ablation_study.py --classifier-backend prompt-guard --perplexity-backend lm --warmup
```

---

## 4. Ablation study — output-defense

**Script:** `output-defense/scripts/run_ablation_study.py`

### Phase 1 stub backends (agent session, 2026-06-25)

Threshold **0.50**, 48 fixtures (30 attacks, 18 benign).

| Omitted detector | Fused ASR | Fused FPR | Δ ASR vs full | Δ FPR vs full |
|------------------|-----------|-----------|---------------|---------------|
| *(none — full)* | 86.7% | 0.0% | — | — |
| toxicity | 60.0% | 0.0% | **+26.7%** | 0.0% |
| pii | 60.0% | 0.0% | **+26.7%** | 0.0% |
| backtranslation | 60.0% | 0.0% | **+26.7%** | 0.0% |

**Interpretation (stub):** All three scoring detectors contribute equally to fused ASR on this set — each catches a disjoint subset; removing any one drops fused ASR by ~27 points.

Reproduce with H2 real backends:

```bash
cd output-defense
python scripts/run_ablation_study.py --toxicity-backend toxic-bert --pii-backend ner --warmup
# Router backtranslation (slow, needs model-router + XAI_API_KEY):
python scripts/run_ablation_study.py --backtranslation-backend router
```

---

## 5. Fixture-level before/after (defense services)

These tables come from H1/H2 README fixture-metrics runs (not the red-team corpus).

### Input-defense (H1)

| Detector | Phase 1 stub ASR | H1 real ASR |
|----------|------------------|-------------|
| classifier | 53.3% | **93.3%** |
| perplexity | 0.0% | **53.3%** |
| **fused** | **83.3%** | **96.7%** |

### Output-defense (H2, local ML, backtranslation=stub)

| Detector | Phase 1 stub ASR | H2 local ML ASR |
|----------|------------------|-----------------|
| fused | 86.7% | 86.7% |

Router-live Grok backtranslation improves semantic drift detection but adds FPR on benign code/prose — see [output-defense/README.md](output-defense/README.md) for calibrated Grok numbers (**your terminal** vs **agent session** runs labeled there).

---

## 6. How to re-run everything

```bash
# Unit tests (mocked defenses + ablation smoke)
make test-python

# Live adaptive campaign
docker compose up -d --build input-defense output-defense redteam
cd redteam && python scripts/run_adaptive_campaign.py --rounds 3

# Ablation (local Python, no Docker required for defense scripts)
cd input-defense && python scripts/run_ablation_study.py --classifier-backend stub --perplexity-backend stub
cd output-defense && python scripts/run_ablation_study.py --toxicity-backend stub --pii-backend regex --backtranslation-backend stub
```

---

## 7. Known limitations after H3

| Gap | Status |
|-----|--------|
| LLM paraphrase mutator via model-router | Not wired; adaptive uses lexical compound mutators |
| HarmBench / AdvBench adapters | Not implemented |
| Phase 1 baseline vs expanded 30-attack corpus | Baseline YAML still 24×8; use `run_before_after.py` for live hardened comparison |
| Embedding dedup for bypass patterns | Postgres column still unused |
| Auto audit emit from campaigns | Manual only |

---

## 8. What H4 will address

- Dashboard auth (dev-grade token/basic auth)
- Go gateway replacing Python SDK proxy on port 8080
- Explicit streaming decision documentation

See the Phase 2 plan in project history for full H4 scope.
