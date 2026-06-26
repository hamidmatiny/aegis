"""Ablation metrics tests (stub backends)."""

from __future__ import annotations

import pytest

from aegis_output_defense.detectors.registry import build_detector_registry
from aegis_output_defense.metrics import compute_ablation_metrics, load_fixtures
from aegis_output_defense.service import OutputDefenseService


@pytest.mark.asyncio
async def test_ablation_full_ensemble_first_row() -> None:
    registry = build_detector_registry(
        toxicity_backend="stub",
        pii_backend="regex",
        backtranslation_backend="stub",
    )
    service = OutputDefenseService(detectors=registry)
    reports = await compute_ablation_metrics(service, load_fixtures())
    assert reports[0].omitted_detector == "(none — full ensemble)"
    assert len(reports) == 4  # full + 3 scoring detectors
