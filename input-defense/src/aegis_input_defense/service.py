"""Input defense orchestration service."""

from __future__ import annotations

from aegis_input_defense.detectors.base import Detector, DetectorContext
from aegis_input_defense.detectors.registry import ALL_DETECTOR_IDS, build_detector_registry
from aegis_input_defense.fusion import build_verdict
from aegis_input_defense.models import DetectorInfo, DetectorResult, InputVerdict


class InputDefenseService:
    """Orchestrates detector execution, fusion, and verdict construction."""

    def __init__(self, detectors: dict[str, Detector] | None = None) -> None:
        self._detectors = detectors or build_detector_registry()

    @property
    def detectors(self) -> dict[str, Detector]:
        return self._detectors

    def list_detectors(self) -> list[DetectorInfo]:
        return [
            DetectorInfo(
                detector_id=d.detector_id,
                detector_version=d.detector_version,
                description=d.description.strip(),
                is_transform=d.is_transform,
            )
            for d in self._detectors.values()
        ]

    async def analyze_detector(
        self,
        detector_id: str,
        text: str,
        *,
        trusted_instruction: str | None = None,
        request_id: str | None = None,
    ) -> DetectorResult:
        detector = self._get_detector(detector_id)
        ctx = DetectorContext(trusted_instruction=trusted_instruction, request_id=request_id)
        return await detector.analyze(text, ctx)

    async def analyze_all(
        self,
        text: str,
        *,
        trusted_instruction: str | None = None,
        enabled_detectors: list[str] | None = None,
        request_id: str | None = None,
    ) -> InputVerdict:
        ids = enabled_detectors or list(ALL_DETECTOR_IDS)
        ctx = DetectorContext(trusted_instruction=trusted_instruction, request_id=request_id)

        results: list[DetectorResult] = []
        for detector_id in ids:
            detector = self._get_detector(detector_id)
            result = await detector.analyze(text, ctx)
            results.append(result)

        return build_verdict(results, request_id=request_id)

    def _get_detector(self, detector_id: str) -> Detector:
        if detector_id not in self._detectors:
            available = ", ".join(sorted(self._detectors))
            raise KeyError(f"Unknown detector {detector_id!r}; available: {available}")
        return self._detectors[detector_id]
