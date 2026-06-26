"""Ablation metrics tests (stub backends)."""

from __future__ import annotations

import pytest

from aegis_input_defense.detectors.registry import build_classifier_backend, build_detector_registry
from aegis_input_defense.metrics import compute_ablation_metrics, load_fixtures
from aegis_input_defense.service import InputDefenseService


@pytest.mark.asyncio
async def test_ablation_full_ensemble_first_row() -> None:
    registry = build_detector_registry(
        classifier_backend=build_classifier_backend("stub"),
        perplexity_backend="stub",
    )
    service = InputDefenseService(detectors=registry)
    reports = await compute_ablation_metrics(service, load_fixtures())
    assert reports[0].omitted_detector == "(none — full ensemble)"
    assert len(reports) == 5  # full + 4 scoring detectors
