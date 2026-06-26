#!/usr/bin/env python3
"""Ablation study: fused ASR/FPR with each detector removed one at a time."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from aegis_input_defense.detectors.registry import build_classifier_backend, build_detector_registry
from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.metrics import (
    compute_ablation_metrics,
    format_ablation_table,
    load_fixtures,
)
from aegis_input_defense.ml.loader import warmup_models
from aegis_input_defense.service import InputDefenseService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--classifier-backend",
        choices=("stub", "prompt-guard"),
        default=os.getenv("AEGIS_INPUT_DEFENSE_CLASSIFIER_BACKEND", "prompt-guard"),
    )
    parser.add_argument(
        "--perplexity-backend",
        choices=("stub", "lm"),
        default=os.getenv("AEGIS_INPUT_DEFENSE_PERPLEXITY_BACKEND", "lm"),
    )
    parser.add_argument("--warmup", action="store_true")
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    if args.warmup:
        warmup_models(
            prompt_guard=args.classifier_backend == "prompt-guard",
            perplexity=args.perplexity_backend == "lm",
        )

    fixtures = load_fixtures()
    registry = build_detector_registry(
        classifier_backend=build_classifier_backend(args.classifier_backend),
        perplexity_backend=args.perplexity_backend,
    )
    service = InputDefenseService(detectors=registry)
    threshold = detection_threshold()

    start = time.perf_counter()
    reports = await compute_ablation_metrics(service, fixtures, threshold=threshold)
    elapsed = time.perf_counter() - start

    attacks = sum(1 for f in fixtures if f.is_attack)
    benign = sum(1 for f in fixtures if f.is_benign)

    print("AEGIS Input Defense — Ablation Study")
    print(f"Backends: classifier={args.classifier_backend}, perplexity={args.perplexity_backend}")
    print(f"Fixtures: {len(fixtures)} total ({attacks} attacks, {benign} benign)")
    print(f"Detection threshold: {threshold:.2f}")
    print(f"Scoring time: {elapsed:.1f}s")
    print()
    print(format_ablation_table(reports))
    print()
    print("Δ ASR: positive means removing the detector lowered catch rate (detector helped).")
    print("Δ FPR: positive means removing the detector lowered false positives.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
