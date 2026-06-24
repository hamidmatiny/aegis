"""Fixture-based ASR and FPR measurement — primary security regression suite."""

from __future__ import annotations

import pytest

from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.metrics import (
    compute_category_metrics,
    compute_metrics,
    format_category_metrics_table,
    format_metrics_table,
)
from aegis_input_defense.service import InputDefenseService


@pytest.mark.asyncio
async def test_fused_asr_above_floor(service: InputDefenseService, all_fixtures) -> None:
    """Fused pipeline must catch at least 60% of fixture attacks at default threshold."""
    reports = await compute_metrics(service, all_fixtures)
    fused = next(r for r in reports if r.detector_id == "fused")
    assert fused.attack_success_rate >= 0.60, (
        f"Fused ASR {fused.attack_success_rate:.1%} below 60% floor"
    )


@pytest.mark.asyncio
async def test_fused_fpr_below_ceiling(service: InputDefenseService, all_fixtures) -> None:
    """Fused pipeline false-positive rate must stay below 40% on fixture benign set."""
    reports = await compute_metrics(service, all_fixtures)
    fused = next(r for r in reports if r.detector_id == "fused")
    assert fused.false_positive_rate <= 0.40, (
        f"Fused FPR {fused.false_positive_rate:.1%} above 40% ceiling"
    )


@pytest.mark.asyncio
async def test_heuristic_asr_above_floor(service: InputDefenseService, all_fixtures) -> None:
    reports = await compute_metrics(service, all_fixtures)
    heuristic = next(r for r in reports if r.detector_id == "heuristic")
    assert heuristic.attack_success_rate >= 0.70


@pytest.mark.asyncio
async def test_print_metrics_report(service: InputDefenseService, all_fixtures, capsys) -> None:
    """Emit full metrics table (visible with pytest -s)."""
    thresh = detection_threshold()
    reports = await compute_metrics(service, all_fixtures, threshold=thresh)
    category_reports = await compute_category_metrics(service, all_fixtures, threshold=thresh)
    table = format_metrics_table(reports)
    category_table = format_category_metrics_table(category_reports)
    print("\n=== AEGIS Input Defense Fixture Metrics ===")
    print(f"Threshold: {thresh:.2f}")
    print("\n-- Aggregate --")
    print(table)
    print("\n-- ASR by Attack Category --")
    print(category_table)
    print("===========================================\n")
    assert "fused" in table
    assert len(reports) == 5
    assert len(category_reports) > 0
    assert "direct injection" in category_table


@pytest.mark.asyncio
async def test_category_metrics_cover_all_attack_categories(
    service: InputDefenseService,
    attack_fixtures,
) -> None:
    categories = {f.category for f in attack_fixtures}
    reports = await compute_category_metrics(service, attack_fixtures)
    report_categories = {r.category for r in reports}
    assert categories == report_categories
    for cat in categories:
        cat_reports = [r for r in reports if r.category == cat]
        assert {r.detector_id for r in cat_reports} == {
            "heuristic",
            "perplexity",
            "known_answer",
            "classifier",
            "fused",
        }
