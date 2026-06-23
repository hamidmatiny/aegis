"""Fixture-based ASR and FPR measurement — primary security regression suite."""

from __future__ import annotations

import pytest

from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.metrics import compute_metrics, format_metrics_table
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
    reports = await compute_metrics(service, all_fixtures, threshold=detection_threshold())
    table = format_metrics_table(reports)
    print("\n=== AEGIS Input Defense Fixture Metrics ===")
    print(f"Threshold: {detection_threshold():.2f}")
    print(table)
    print("===========================================\n")
    assert "fused" in table
    assert len(reports) == 5
