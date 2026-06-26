"""Tests for single-pass fixture scoring."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from aegis_output_defense.metrics import (
    compute_metrics_from_rows,
    score_fixtures,
)
from aegis_output_defense.models import DetectorScore, FixtureCase, OutputVerdict, VerdictAction


@pytest.mark.asyncio
async def test_score_fixtures_single_pass() -> None:
    fixtures = [
        FixtureCase(
            id="atk-1",
            label="attack",
            category="toxic_content",
            description="x",
            content="bad",
        ),
        FixtureCase(
            id="ben-1",
            label="benign",
            category="helpful",
            description="y",
            content="good",
        ),
    ]
    service = AsyncMock()
    service.analyze_all = AsyncMock(
        side_effect=[
            OutputVerdict(
                action=VerdictAction.BLOCK,
                fused_score=0.9,
                detector_scores=[
                    DetectorScore(
                        detector_id="toxicity",
                        detector_version="v1",
                        score=0.8,
                        reasoning="tox",
                        latency_ms=1,
                        metadata={"execution_backend": "stub-patterns"},
                    ),
                    DetectorScore(
                        detector_id="pii",
                        detector_version="v1",
                        score=0.1,
                        reasoning="pii",
                        latency_ms=1,
                        metadata={"execution_backend": "regex"},
                    ),
                    DetectorScore(
                        detector_id="backtranslation",
                        detector_version="v1",
                        score=0.7,
                        reasoning="bt",
                        latency_ms=1,
                        metadata={"execution_backend": "router-live"},
                    ),
                ],
            ),
            OutputVerdict(
                action=VerdictAction.ALLOW,
                fused_score=0.1,
                detector_scores=[
                    DetectorScore(
                        detector_id="toxicity",
                        detector_version="v1",
                        score=0.05,
                        reasoning="tox",
                        latency_ms=1,
                        metadata={"execution_backend": "stub-patterns"},
                    ),
                    DetectorScore(
                        detector_id="pii",
                        detector_version="v1",
                        score=0.05,
                        reasoning="pii",
                        latency_ms=1,
                        metadata={"execution_backend": "regex"},
                    ),
                    DetectorScore(
                        detector_id="backtranslation",
                        detector_version="v1",
                        score=0.05,
                        reasoning="bt",
                        latency_ms=1,
                        metadata={"execution_backend": "router-live"},
                    ),
                ],
            ),
        ]
    )

    progress_calls: list[str] = []

    def on_progress(index: int, total: int, case: FixtureCase, elapsed: float) -> None:
        progress_calls.append(case.id)

    rows = await score_fixtures(service, fixtures, on_progress=on_progress)
    assert service.analyze_all.await_count == 2
    assert len(rows) == 2
    assert progress_calls == ["atk-1", "ben-1"]

    reports = compute_metrics_from_rows(rows, threshold=0.5)
    backtrans = next(r for r in reports if r.detector_id == "backtranslation")
    assert backtrans.attack_success_rate == 1.0
    assert backtrans.false_positive_rate == 0.0
