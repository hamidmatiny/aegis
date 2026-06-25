"""Backtranslation consistency check for semantic smoothing."""

from __future__ import annotations

import time

from aegis_output_defense.detectors.backtranslation.backend import BacktranslationBackend
from aegis_output_defense.detectors.backtranslation.stub_backend import StubBacktranslationBackend
from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.models import DetectorResult


class BacktranslationDetector(Detector):
    """Detect semantic drift via restatement divergence or pattern stub."""

    def __init__(self, backend: BacktranslationBackend | None = None) -> None:
        self._backend = backend or StubBacktranslationBackend()

    @property
    def detector_id(self) -> str:
        return "backtranslation"

    @property
    def detector_version(self) -> str:
        return "2.0.0-router" if "router" in self._backend.model_id else "1.0.0-stub"

    async def analyze(self, content: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        original_prompt = context.original_prompt if context else None
        result = await self._backend.evaluate(content, original_prompt=original_prompt)
        latency = int((time.perf_counter() - start) * 1000)
        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=result.score,
            reasoning=result.reasoning,
            latency_ms=latency,
            metadata={"model_id": result.model_id, **result.metadata},
        )
