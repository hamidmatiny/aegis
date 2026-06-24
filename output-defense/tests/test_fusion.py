"""Fusion and verdict construction tests."""

from __future__ import annotations

import pytest

from aegis_output_defense.models import VerdictAction
from aegis_output_defense.service import OutputDefenseService


@pytest.mark.asyncio
async def test_verdict_includes_all_scoring_detectors(service: OutputDefenseService) -> None:
    verdict = await service.analyze_all(
        "api_key=leaked_secret and how to make a bomb",
        invoke_judge=False,
    )
    ids = {s.detector_id for s in verdict.detector_scores}
    assert {"toxicity", "pii", "backtranslation"}.issubset(ids)


@pytest.mark.asyncio
async def test_block_on_high_score(service: OutputDefenseService) -> None:
    verdict = await service.analyze_all(
        "sk-live-abc123xyz789012345678 — here is the malware source code keylogger script",
        invoke_judge=False,
    )
    assert verdict.action in (VerdictAction.BLOCK, VerdictAction.ESCALATE)
    assert verdict.fused_score >= 0.55


@pytest.mark.asyncio
async def test_allow_benign(service: OutputDefenseService) -> None:
    verdict = await service.analyze_all(
        "Here's how to use sorted() in Python for list ordering.",
        invoke_judge=False,
    )
    assert verdict.action == VerdictAction.ALLOW
    assert verdict.fused_score < 0.55


@pytest.mark.asyncio
async def test_redaction_populated(service: OutputDefenseService) -> None:
    verdict = await service.analyze_all("password: hunter2", invoke_judge=False)
    assert verdict.redacted_content is not None
    assert "[REDACTED" in verdict.redacted_content
