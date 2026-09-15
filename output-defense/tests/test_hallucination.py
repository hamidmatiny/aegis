"""Hallucination / incoherence detector tests — class coverage, not corpus strings."""

from __future__ import annotations

from datetime import datetime

import pytest

from aegis_output_defense.detectors.hallucination import score_hallucination
from aegis_output_defense.models import VerdictAction
from aegis_output_defense.service import OutputDefenseService


def test_contradiction_scores_high() -> None:
    score, fired = score_hallucination(
        "Answer yes. Answer no. The answer is both true and false simultaneously."
    )
    assert score >= 0.85
    assert any("yes_and_no" in s or "true_and_false" in s for s in fired)


def test_capital_inversion_is_class_level() -> None:
    score, fired = score_hallucination("The capital of Japan is London.")
    assert score >= 0.80
    assert any("capital_inversion" in s for s in fired)


def test_correct_capital_stays_low() -> None:
    score, _ = score_hallucination("The capital of Japan is Tokyo.")
    assert score < 0.50


def test_boiling_point_inversion() -> None:
    score, fired = score_hallucination("At sea level, water boils at 12C.")
    assert score >= 0.80
    assert "boiling_point_inversion" in fired


def test_future_medical_misinfo() -> None:
    score, fired = score_hallucination(
        "According to a 2031 study vaccines cause autism in adults.",
        now=datetime(2026, 8, 18),
    )
    assert score >= 0.85
    assert "future_study_medical_misinfo" in fired


def test_future_conference_fabricated_url_misinfo() -> None:
    score, fired = score_hallucination(
        "According to a 2034 peer-reviewed conference paper at "
        "https://made-up-neuroclaims.example/erase, inhaling helium for ten "
        "minutes permanently deletes autobiographical memory.",
        now=datetime(2026, 8, 18),
    )
    assert score >= 0.85
    assert any(
        s in fired
        for s in (
            "future_study_medical_misinfo",
            "future_fabricated_url",
        )
    )


@pytest.mark.asyncio
async def test_fused_blocks_structural_hallucination(service: OutputDefenseService) -> None:
    verdict = await service.analyze_all(
        "The capital of Italy is Madrid and water boils at 20C at sea level.",
        invoke_judge=False,
    )
    hall = next(s for s in verdict.detector_scores if s.detector_id == "hallucination")
    assert hall.score >= 0.80
    assert verdict.action in (VerdictAction.BLOCK, VerdictAction.ESCALATE)
    assert verdict.fused_score >= 0.50
