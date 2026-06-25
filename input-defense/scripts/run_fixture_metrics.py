#!/usr/bin/env python3
"""Run fixture metrics with explicit backend selection."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from aegis_input_defense.detectors.registry import build_classifier_backend, build_detector_registry
from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.metrics import (
    compute_category_metrics,
    compute_metrics,
    format_category_metrics_table,
    format_metrics_table,
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
    parser.add_argument("--warmup", action="store_true", help="Pre-load ML models before scoring")
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
    reports = await compute_metrics(service, fixtures, threshold=threshold)
    category_reports = await compute_category_metrics(service, fixtures, threshold=threshold)
    elapsed = time.perf_counter() - start

    attacks = sum(1 for f in fixtures if f.is_attack)
    benign = sum(1 for f in fixtures if f.is_benign)

    print("AEGIS Input Defense — Fixture Metrics Report")
    print(
        f"Backends: classifier={args.classifier_backend}, perplexity={args.perplexity_backend}"
    )
    print(f"Fixtures: {len(fixtures)} total ({attacks} attacks, {benign} benign)")
    print(f"Detection threshold: {threshold:.2f}")
    print(f"Scoring time: {elapsed:.1f}s")
    print()
    print("-- Aggregate --")
    print(format_metrics_table(reports))
    print()
    print("-- ASR by Attack Category --")
    print(format_category_metrics_table(category_reports))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
