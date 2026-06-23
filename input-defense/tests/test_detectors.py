"""Test each detector in isolation against fixtures."""

from __future__ import annotations

import pytest

from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.models import FixtureCase
from aegis_input_defense.service import InputDefenseService

DETECTOR_IDS = ["heuristic", "perplexity", "known_answer", "classifier"]


@pytest.mark.asyncio
@pytest.mark.parametrize("detector_id", DETECTOR_IDS)
async def test_detector_returns_scored_result(
    service: InputDefenseService,
    attack_fixtures: list[FixtureCase],
    detector_id: str,
) -> None:
    case = attack_fixtures[0]
    result = await service.analyze_detector(detector_id, case.text.strip())
    assert result.detector_id == detector_id
    assert 0.0 <= result.score <= 1.0
    assert result.reasoning
    assert result.latency_ms >= 0


@pytest.mark.asyncio
@pytest.mark.parametrize("detector_id", DETECTOR_IDS)
async def test_detector_catches_majority_of_direct_injections(
    service: InputDefenseService,
    all_fixtures: list[FixtureCase],
    detector_id: str,
) -> None:
    """Direct injection is the baseline attack class — expect reasonable recall."""
    direct = [f for f in all_fixtures if f.category == "direct_injection" and f.is_attack]
    thresh = detection_threshold()
    caught = 0
    for case in direct:
        result = await service.analyze_detector(detector_id, case.text.strip())
        if result.score >= thresh:
            caught += 1
    # At least heuristic and known_answer should catch most direct injections
    if detector_id in ("heuristic", "known_answer", "classifier"):
        assert caught >= len(direct) * 0.6, (
            f"{detector_id} caught only {caught}/{len(direct)} direct injections"
        )


@pytest.mark.asyncio
async def test_spotlighting_produces_transform(service: InputDefenseService) -> None:
    text = "[Retrieved document: report.txt]\nSome data.\nSummarize."
    result = await service.analyze_detector("spotlighting", text)
    assert result.transformed_text is not None
    assert "UNTRUSTED_DATA" in result.transformed_text
    assert result.metadata.get("transform_applied") == "true"


@pytest.mark.asyncio
async def test_classifier_backend_is_swappable() -> None:
    from aegis_input_defense.detectors.classifier import (
        ClassifierBackend,
        ClassifierDetector,
        ClassifierPrediction,
    )

    class AlwaysAttackBackend(ClassifierBackend):
        @property
        def model_id(self) -> str:
            return "test-always-attack"

        async def predict(self, text: str) -> ClassifierPrediction:
            return ClassifierPrediction(
                label="injection",
                probability=0.99,
                reasoning="test backend",
                model_id=self.model_id,
            )

    detector = ClassifierDetector(backend=AlwaysAttackBackend())
    result = await detector.analyze("hello")
    assert result.score == 0.99
    assert result.metadata["model_id"] == "test-always-attack"
