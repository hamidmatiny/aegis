"""LLM-judge ensemble — invoked only on ambiguous fused scores."""

from __future__ import annotations

import time

from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.detectors.judge.backend import JudgeBackend
from aegis_output_defense.detectors.judge.stub_backend import StubJudgeBackend
from aegis_output_defense.models import DetectorResult, JudgeVote


class JudgeDetector(Detector):
    """Multi-judge ensemble for ambiguous outputs (cost-controlled)."""

    def __init__(self, backend: JudgeBackend | None = None) -> None:
        self._backend = backend or StubJudgeBackend()

    @property
    def detector_id(self) -> str:
        return "judge"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def conditional(self) -> bool:
        return True

    async def analyze(self, content: str, context: DetectorContext | None = None) -> DetectorResult:
        result, _ = await self.analyze_with_votes(content, fused_score=0.0, context=context)
        return result

    async def analyze_with_votes(
        self,
        content: str,
        *,
        fused_score: float,
        context: DetectorContext | None = None,
    ) -> tuple[DetectorResult, list[JudgeVote]]:
        from aegis_output_defense.detectors.judge.backend import JudgeEnsembleResult

        start = time.perf_counter()
        ensemble: JudgeEnsembleResult = await self._backend.evaluate(
            content, fused_score=fused_score
        )
        latency = int((time.perf_counter() - start) * 1000)
        result = DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=ensemble.boosted_score,
            reasoning=ensemble.reasoning,
            latency_ms=latency,
            metadata={"model_id": self._backend.model_id},
        )
        return result, ensemble.votes
