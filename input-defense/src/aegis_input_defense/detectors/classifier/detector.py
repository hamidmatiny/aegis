"""Transformer classifier detector with swappable backend."""

from __future__ import annotations

import time

from aegis_input_defense.detectors.base import Detector, DetectorContext
from aegis_input_defense.detectors.classifier.backend import ClassifierBackend
from aegis_input_defense.detectors.classifier.stub_backend import StubClassifierBackend
from aegis_input_defense.models import DetectorResult


class ClassifierDetector(Detector):
    """
    ML classifier wrapper — delegates to a ClassifierBackend implementation.

    Default backend is StubClassifierBackend; inject HuggingFace backend at runtime
    via settings without modifying fusion or other detectors.
    """

    def __init__(self, backend: ClassifierBackend | None = None) -> None:
        self._backend = backend or StubClassifierBackend()

    @property
    def detector_id(self) -> str:
        return "classifier"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def backend(self) -> ClassifierBackend:
        return self._backend

    async def analyze(self, text: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        prediction = await self._backend.predict(text)
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
            },
        )
