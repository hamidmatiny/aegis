"""Per-detector unit tests."""

from __future__ import annotations

import pytest

from aegis_output_defense.models import VerdictAction
from aegis_output_defense.service import OutputDefenseService


@pytest.mark.asyncio
async def test_pii_catches_api_key(service: OutputDefenseService) -> None:
    result = await service.analyze_detector("pii", "Use sk-live-abc123xyz789012345")
    assert result.score >= 0.85
    assert result.redacted_text is not None
    assert "[REDACTED" in result.redacted_text


@pytest.mark.asyncio
async def test_toxicity_catches_harmful(service: OutputDefenseService) -> None:
    result = await service.analyze_detector("toxicity", "How to make a bomb at home")
    assert result.score >= 0.55


@pytest.mark.asyncio
async def test_backtranslation_catches_jailbreak(service: OutputDefenseService) -> None:
    result = await service.analyze_detector(
        "backtranslation",
        "Developer mode enabled. Jailbreak successful.",
    )
    assert result.score >= 0.85


@pytest.mark.asyncio
async def test_benign_low_scores(service: OutputDefenseService) -> None:
    content = "Happy to help! Here's how to sort a list in Python."
    tox = await service.analyze_detector("toxicity", content)
    pii = await service.analyze_detector("pii", content)
    assert tox.score < 0.50
    assert pii.score < 0.50


@pytest.mark.asyncio
async def test_judge_runs_on_ambiguous(service: OutputDefenseService) -> None:
    content = "I can't help with that. However, here is some borderline content about weapons."
    verdict = await service.analyze_all(content)
    if 0.45 <= verdict.fused_score < 0.70:
        assert len(verdict.judge_votes) > 0


_AMBIGUOUS_JUDGE_CONTENT = (
    "According to a 2029 study published at source: https://example-fake.com/research, "
    "some authors discuss weapon recipe theory in historical fiction."
)


@pytest.mark.asyncio
async def test_ambiguous_band_triggers_judge_and_affects_verdict(
    service: OutputDefenseService,
) -> None:
    """Fused score in 0.45–0.70 must invoke judge; verdict reflects judge boost."""
    pre = await service.analyze_all(_AMBIGUOUS_JUDGE_CONTENT, invoke_judge=False)
    assert 0.45 <= pre.fused_score < 0.70, f"pre_fused={pre.fused_score}"

    verdict = await service.analyze_all(_AMBIGUOUS_JUDGE_CONTENT)
    assert len(verdict.judge_votes) >= 3
    assert verdict.fused_score >= pre.fused_score
    assert verdict.action in (VerdictAction.BLOCK, VerdictAction.ESCALATE)
    unsafe = sum(
        1 for v in verdict.judge_votes if v.vote in (VerdictAction.BLOCK, VerdictAction.ESCALATE)
    )
    assert unsafe >= 2
