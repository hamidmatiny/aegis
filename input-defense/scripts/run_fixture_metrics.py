#!/usr/bin/env python3
"""Run fixture set and print ASR/FPR metrics table."""

from __future__ import annotations

import asyncio
import sys

from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.metrics import compute_metrics, format_metrics_table, load_fixtures
from aegis_input_defense.service import InputDefenseService


async def main() -> int:
    fixtures = load_fixtures()
    service = InputDefenseService()
    threshold = detection_threshold()
    reports = await compute_metrics(service, fixtures, threshold=threshold)

    attacks = sum(1 for f in fixtures if f.is_attack)
    benign = sum(1 for f in fixtures if f.is_benign)

    print("AEGIS Input Defense — Fixture Metrics Report")
    print(f"Fixtures: {len(fixtures)} total ({attacks} attacks, {benign} benign)")
    print(f"Detection threshold: {threshold:.2f}")
    print()
    print(format_metrics_table(reports))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
