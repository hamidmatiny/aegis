"""Toxicity and safety classifier for harmful model outputs."""

from __future__ import annotations

import time

from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.detectors.toxicity.backend import ToxicityBackend
from aegis_output_defense.detectors.toxicity.stub_backend import StubToxicityBackend
from aegis_output_defense.models import DetectorResult


class ToxicityDetector(Detector):
    """Safety/toxicity classifier via swappable backend (stub by default)."""

    def __init__(self, backend: ToxicityBackend | None = None) -> None:
        self._backend = backend or StubToxicityBackend()

    @property
    def detector_id(self) -> str:
        return "toxicity"

    @property
    def detector_version(self) -> str:
        model_id = self._backend.model_id
        return (
            "2.0.0-toxic-bert"
            if "toxic-bert" in model_id or "unitary" in model_id
            else "1.0.0-stub"
        )

    async def analyze(self, content: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        prediction = await self._backend.predict(content)
        latency = int((time.perf_counter() - start) * 1000)
        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=prediction.probability,
            reasoning=prediction.reasoning,
            latency_ms=latency,
            metadata={
                "model_id": prediction.model_id,
                "label": prediction.label,
                **(prediction.metadata or {}),
            },
        )
