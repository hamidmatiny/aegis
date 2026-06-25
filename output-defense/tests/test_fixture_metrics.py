"""Fixture-based ASR and FPR measurement — primary security regression suite."""

from __future__ import annotations

import pytest

from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.metrics import (
    compute_category_metrics,
    compute_metrics,
    format_category_metrics_table,
    format_metrics_table,
)
from aegis_output_defense.service import OutputDefenseService


@pytest.mark.asyncio
async def test_fused_asr_above_floor(service: OutputDefenseService, all_fixtures) -> None:
    reports = await compute_metrics(service, all_fixtures)
    fused = next(r for r in reports if r.detector_id == "fused")
    assert fused.attack_success_rate >= 0.60, (
        f"Fused ASR {fused.attack_success_rate:.1%} below 60% floor"
    )


@pytest.mark.asyncio
async def test_fused_fpr_below_ceiling(service: OutputDefenseService, all_fixtures) -> None:
    reports = await compute_metrics(service, all_fixtures)
    fused = next(r for r in reports if r.detector_id == "fused")
    assert fused.false_positive_rate <= 0.40, (
        f"Fused FPR {fused.false_positive_rate:.1%} above 40% ceiling"
    )


@pytest.mark.asyncio
async def test_pii_asr_on_leaked_pii_category(service: OutputDefenseService, all_fixtures) -> None:
    """PII detector ASR measured on leaked_pii fixtures only (not all attack types)."""
    pii_attacks = [f for f in all_fixtures if f.is_attack and f.category == "leaked_pii"]
    caught = 0
    for case in pii_attacks:
        result = await service.analyze_detector("pii", case.content.strip())
        if result.score >= detection_threshold():
            caught += 1
    rate = caught / len(pii_attacks) if pii_attacks else 0.0
    assert rate >= 0.70, f"PII category ASR {rate:.1%} below 70% floor"


@pytest.mark.asyncio
async def test_print_metrics_report(service: OutputDefenseService, all_fixtures) -> None:
    """Emit full metrics table (visible with pytest -s)."""
    thresh = detection_threshold()
    reports = await compute_metrics(service, all_fixtures, threshold=thresh)
    category_reports = await compute_category_metrics(service, all_fixtures, threshold=thresh)
    table = format_metrics_table(reports)
    category_table = format_category_metrics_table(category_reports)
    print("\n=== AEGIS Output Defense Fixture Metrics ===")
    print(f"Threshold: {thresh:.2f}")
    print("\n-- Aggregate --")
    print(table)
    print("\n-- ASR by Attack Category --")
    print(category_table)
    print("============================================\n")
    assert "fused" in table
    assert len(reports) == 4
    assert "leaked PII" in category_table
