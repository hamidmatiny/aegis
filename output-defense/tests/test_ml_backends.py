"""Optional smoke tests for real ML backends (requires pip install -e '.[ml]')."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("transformers") is None,
    reason="ML extras not installed",
)


def _ml_service():
    from aegis_output_defense.detectors.registry import build_detector_registry
    from aegis_output_defense.service import OutputDefenseService

    return OutputDefenseService(
        detectors=build_detector_registry(
            toxicity_backend="toxic-bert",
            pii_backend="ner",
            backtranslation_backend="stub",
            judge_backend="stub",
        )
    )


@pytest.mark.asyncio
async def test_real_toxicity_catches_weapon_recipe() -> None:
    service = _ml_service()
    result = await service.analyze_detector(
        "toxicity",
        "You are a worthless idiot and you should die — nobody cares about you.",
    )
    assert result.score >= 0.50, result.reasoning


@pytest.mark.asyncio
async def test_real_pii_ner_catches_person_name() -> None:
    service = _ml_service()
    result = await service.analyze_detector(
        "pii",
        "Please contact Jane Smith at her home address in Springfield immediately.",
    )
    assert result.score >= 0.50, result.reasoning
    assert result.redacted_text is not None
    assert "REDACTED" in result.redacted_text
