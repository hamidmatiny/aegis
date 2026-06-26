"""Adaptive multi-round campaign tests."""

from __future__ import annotations

import pytest

from aegis_redteam.models import RunAdaptiveCampaignRequest


@pytest.mark.asyncio
async def test_adaptive_campaign_three_rounds(mock_service) -> None:
    result = await mock_service.run_adaptive_campaign(
        RunAdaptiveCampaignRequest(
            rounds=3,
            strategies=["identity", "paraphrase"],
            store_bypasses=False,
            max_variants_per_bypass=2,
        )
    )
    report = result.report
    assert len(report.rounds) == 3
    assert report.rounds[0].total_probes > 0
    assert report.rounds[0].variants_generated == 0
    # Round 2+ may have zero probes if round 1 had no bypasses under mock defenses
    assert report.total_probes >= report.rounds[0].total_probes


@pytest.mark.asyncio
async def test_adaptive_round_metadata(mock_service) -> None:
    result = await mock_service.run_adaptive_campaign(
        RunAdaptiveCampaignRequest(rounds=2, strategies=["identity"], store_bypasses=False)
    )
    baseline = [r for r in result.report.results if r.metadata.get("phase") == "baseline"]
    adaptive = [r for r in result.report.results if r.metadata.get("phase") == "adaptive"]
    assert baseline
    assert all(r.metadata.get("round") == "1" for r in baseline)
    if adaptive:
        assert all(r.metadata.get("round") == "2" for r in adaptive)
        assert all(r.strategy.startswith("adaptive:") for r in adaptive)
