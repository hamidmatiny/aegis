#!/usr/bin/env python3
"""Run attack corpus against live defense services and print bypass metrics."""

from __future__ import annotations

import asyncio
import sys

from aegis_redteam.metrics import compute_metrics, format_category_table, format_metrics_table, load_fixtures
from aegis_redteam.models import RunCampaignRequest
from aegis_redteam.probe.client import DefenseClient
from aegis_redteam.service import RedTeamService
from aegis_redteam.settings import settings


async def main() -> int:
    fixtures = load_fixtures()
    attacks = [f for f in fixtures if f.is_attack]
    client = DefenseClient(settings.input_defense_url, settings.output_defense_url)
    service = RedTeamService(
        client,
        threshold=settings.detection_threshold,
        database_url=settings.database_url,
        store_bypasses=settings.store_bypasses,
    )
    try:
        result = await service.run_campaign(RunCampaignRequest())
    finally:
        await client.close()

    report = result.report
    metrics = compute_metrics(report.results, threshold=report.threshold)

    print("AEGIS Red Team — Fixture Bypass Report")
    print(f"Fixtures: {len(attacks)} attacks × {len({r.strategy for r in report.results})} strategies")
    print(f"Detection threshold: {report.threshold:.2f}")
    print(f"Overall bypass rate: {report.bypass_rate:.1%} ({report.bypass_count}/{report.total_probes})")
    print(f"Patterns stored: {result.patterns_stored}")
    print()
    print("-- By Target & Strategy --")
    print(format_metrics_table(metrics))
    print()
    print("-- Bypass Rate by Category --")
    print(format_category_table(report))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
