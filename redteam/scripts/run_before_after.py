#!/usr/bin/env python3
"""Compare Phase 1 stub bypass baseline vs Phase 2 hardened adaptive campaign."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from aegis_redteam.metrics import compute_metrics, format_before_after_table, format_metrics_table
from aegis_redteam.models import RunAdaptiveCampaignRequest
from aegis_redteam.probe.client import DefenseClient
from aegis_redteam.service import RedTeamService
from aegis_redteam.settings import settings

BASELINE_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "aegis_redteam"
    / "baselines"
    / "phase1_stub_bypass.yaml"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=settings.adaptive_rounds)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help="Phase 1 stub bypass baseline YAML",
    )
    return parser.parse_args()


def _load_baseline(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main() -> int:
    args = _parse_args()
    baseline = _load_baseline(args.baseline)

    client = DefenseClient(settings.input_defense_url, settings.output_defense_url)
    service = RedTeamService(
        client,
        threshold=settings.detection_threshold,
        database_url=settings.database_url,
        store_bypasses=False,
    )

    print("Running Phase 2 adaptive campaign against live defenses...", file=sys.stderr)
    try:
        result = await service.run_adaptive_campaign(
            RunAdaptiveCampaignRequest(rounds=args.rounds, store_bypasses=False)
        )
    finally:
        await client.close()

    report = result.report
    baseline_rows = [r for r in report.results if r.metadata.get("phase") == "baseline"]
    adaptive_rows = [r for r in report.results if r.metadata.get("phase") == "adaptive"]
    metrics = compute_metrics(report.results, threshold=report.threshold)

    phase1 = baseline["overall"]
    print("AEGIS Red Team — Phase 1 vs Phase 2 Bypass Comparison")
    print(f"Baseline file: {args.baseline}")
    print(f"Live campaign: {report.campaign_id}")
    print(f"Threshold: {report.threshold:.2f}")
    print()
    print(
        format_before_after_table(
            phase1_bypass_rate=float(phase1["bypass_rate"]),
            phase1_probes=int(phase1["total_probes"]),
            phase1_bypasses=int(phase1["bypass_count"]),
            hardened_bypass_rate=report.baseline_bypass_rate,
            hardened_probes=len(baseline_rows),
            hardened_bypasses=sum(1 for r in baseline_rows if r.bypassed),
            adaptive_bypass_rate=report.adaptive_bypass_rate,
            adaptive_probes=len(adaptive_rows),
            adaptive_bypasses=sum(1 for r in adaptive_rows if r.bypassed),
        )
    )
    print()
    print("-- Phase 2 by target & strategy --")
    print(format_metrics_table(metrics))
    print()
    print("-- Phase 1 baseline by target (stored) --")
    print(json.dumps(baseline.get("by_target", {}), indent=2))
    print()
    print(f"Phase 1 notes: {baseline.get('notes', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
