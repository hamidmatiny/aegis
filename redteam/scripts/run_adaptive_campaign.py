#!/usr/bin/env python3
"""Run multi-round adaptive red-team campaign against live defenses."""

from __future__ import annotations

import argparse
import asyncio
import sys

from aegis_redteam.metrics import (
    compute_metrics,
    format_before_after_table,
    format_category_table,
    format_metrics_table,
    format_round_table,
    load_fixtures,
)
from aegis_redteam.models import RunAdaptiveCampaignRequest
from aegis_redteam.probe.client import DefenseClient
from aegis_redteam.service import RedTeamService
from aegis_redteam.settings import settings


def _configure_streaming_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(line_buffering=True)
            except (ValueError, OSError):
                pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=settings.adaptive_rounds)
    parser.add_argument(
        "--max-variants-per-bypass",
        type=int,
        default=settings.adaptive_max_variants_per_bypass,
    )
    parser.add_argument(
        "--strategies",
        nargs="*",
        default=None,
        help="Baseline round strategies (default: all)",
    )
    return parser.parse_args()


async def main() -> int:
    _configure_streaming_output()
    args = _parse_args()
    attacks = [f for f in load_fixtures() if f.is_attack]

    client = DefenseClient(settings.input_defense_url, settings.output_defense_url)
    service = RedTeamService(
        client,
        threshold=settings.detection_threshold,
        database_url=settings.database_url,
        store_bypasses=settings.store_bypasses,
    )

    print(
        f"Starting adaptive campaign ({args.rounds} rounds, {len(attacks)} attack fixtures)...",
        file=sys.stderr,
        flush=True,
    )

    try:
        result = await service.run_adaptive_campaign(
            RunAdaptiveCampaignRequest(
                rounds=args.rounds,
                max_variants_per_bypass=args.max_variants_per_bypass,
                strategies=args.strategies,
            )
        )
    finally:
        await client.close()

    report = result.report
    metrics = compute_metrics(report.results, threshold=report.threshold)

    baseline_rows = [r for r in report.results if r.metadata.get("phase") == "baseline"]
    adaptive_rows = [r for r in report.results if r.metadata.get("phase") == "adaptive"]
    baseline_bypasses = sum(1 for r in baseline_rows if r.bypassed)
    adaptive_bypasses = sum(1 for r in adaptive_rows if r.bypassed)

    print("AEGIS Red Team — Adaptive Campaign Report")
    print(f"Campaign: {report.campaign_id}")
    print(f"Rounds: {args.rounds} | Threshold: {report.threshold:.2f}")
    print(
        f"Overall bypass rate: {report.bypass_rate:.1%} "
        f"({report.bypass_count}/{report.total_probes})"
    )
    print(f"Patterns stored: {result.patterns_stored}")
    print()
    print("-- Per-round summary --")
    print(format_round_table(report.rounds))
    print()
    print("-- Before/after phases (within this run) --")
    print(
        format_before_after_table(
            phase1_bypass_rate=0.0,
            phase1_probes=0,
            phase1_bypasses=0,
            hardened_bypass_rate=report.baseline_bypass_rate,
            hardened_probes=len(baseline_rows),
            hardened_bypasses=baseline_bypasses,
            adaptive_bypass_rate=report.adaptive_bypass_rate,
            adaptive_probes=len(adaptive_rows),
            adaptive_bypasses=adaptive_bypasses,
        )
    )
    print()
    print("-- By Target & Strategy --")
    print(format_metrics_table(metrics))
    print()
    print("-- Bypass Rate by Category --")
    print(format_category_table(report))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
