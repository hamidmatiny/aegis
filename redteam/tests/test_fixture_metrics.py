"""Fixture-based bypass rate measurement."""

from __future__ import annotations

import pytest

from aegis_redteam.metrics import compute_metrics, format_category_table, format_metrics_table
from aegis_redteam.models import RunCampaignRequest


@pytest.mark.asyncio
async def test_campaign_produces_metrics(mock_service) -> None:
    result = await mock_service.run_campaign(
        RunCampaignRequest(strategies=["identity", "paraphrase"])
    )
    reports = compute_metrics(result.report.results, threshold=result.report.threshold)
    assert len(reports) > 0
    assert all(r.attack_total > 0 for r in reports)


@pytest.mark.asyncio
async def test_identity_bypass_rate_below_ceiling(mock_service) -> None:
    """With mock defenses, identity mutations should not bypass everything."""
    result = await mock_service.run_campaign(RunCampaignRequest(strategies=["identity"]))
    identity_rows = [r for r in result.report.results if r.strategy == "identity"]
    bypass_rate = sum(1 for r in identity_rows if r.bypassed) / len(identity_rows)
    assert bypass_rate <= 0.85, f"Identity bypass rate {bypass_rate:.1%} unexpectedly high"


@pytest.mark.asyncio
async def test_print_metrics_report(mock_service, capsys) -> None:
    result = await mock_service.run_campaign(
        RunCampaignRequest(strategies=["identity", "roleplay"])
    )
    reports = compute_metrics(result.report.results, threshold=result.report.threshold)
    table = format_metrics_table(reports)
    category_table = format_category_table(result.report)
    print("\n=== AEGIS Red Team Fixture Metrics ===")
    print(f"Threshold: {result.report.threshold:.2f}")
    print(f"Overall bypass rate: {result.report.bypass_rate:.1%}")
    print("\n-- By Target & Strategy --")
    print(table)
    print("\n-- Bypass Rate by Category --")
    print(category_table)
    print("======================================\n")
    assert "input_defense" in table
    assert len(result.report.by_category) > 0
