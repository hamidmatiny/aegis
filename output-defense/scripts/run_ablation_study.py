#!/usr/bin/env python3
"""Ablation study: fused ASR/FPR with each detector removed one at a time."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from aegis_output_defense.detectors.registry import build_detector_registry
from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.metrics import (
    compute_ablation_metrics,
    format_ablation_table,
    load_fixtures,
)
from aegis_output_defense.ml.loader import warmup_models
from aegis_output_defense.service import OutputDefenseService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--toxicity-backend",
        choices=("stub", "toxic-bert"),
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_TOXICITY_BACKEND", "toxic-bert"),
    )
    parser.add_argument(
        "--pii-backend",
        choices=("regex", "ner"),
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_PII_BACKEND", "ner"),
    )
    parser.add_argument(
        "--backtranslation-backend",
        choices=("stub", "router"),
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_BACKEND", "stub"),
    )
    parser.add_argument("--warmup", action="store_true")
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    if args.warmup:
        warmup_models(
            toxicity=args.toxicity_backend == "toxic-bert",
            pii_ner=args.pii_backend == "ner",
        )

    fixtures = load_fixtures()
    registry = build_detector_registry(
        toxicity_backend=args.toxicity_backend,
        pii_backend=args.pii_backend,
        backtranslation_backend=args.backtranslation_backend,
    )
    service = OutputDefenseService(detectors=registry)
    threshold = detection_threshold()

    start = time.perf_counter()
    reports = await compute_ablation_metrics(service, fixtures, threshold=threshold)
    elapsed = time.perf_counter() - start

    attacks = sum(1 for f in fixtures if f.is_attack)
    benign = sum(1 for f in fixtures if f.is_benign)

    print("AEGIS Output Defense — Ablation Study")
    print(
        f"Backends: toxicity={args.toxicity_backend}, pii={args.pii_backend}, "
        f"backtranslation={args.backtranslation_backend}"
    )
    print(f"Fixtures: {len(fixtures)} total ({attacks} attacks, {benign} benign)")
    print(f"Detection threshold: {threshold:.2f}")
    print(f"Scoring time: {elapsed:.1f}s")
    print()
    print(format_ablation_table(reports))
    print()
    print("Δ ASR: positive means removing the detector lowered catch rate (detector helped).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
