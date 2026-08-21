"""Input defense orchestration service."""

from __future__ import annotations

import asyncio

from aegis_input_defense.detectors.base import Detector, DetectorContext
from aegis_input_defense.detectors.registry import ALL_DETECTOR_IDS, build_detector_registry
from aegis_input_defense.fusion import build_verdict
from aegis_input_defense.models import DetectorInfo, DetectorResult, InputVerdict
from aegis_input_defense.normalize import expand_scan_surfaces


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
        if detector.is_transform:
            return await detector.analyze(text, ctx)
        return await self._analyze_on_surfaces(detector, text, ctx)

    async def _analyze_on_surfaces(
        self,
        detector: Detector,
        text: str,
        ctx: DetectorContext,
    ) -> DetectorResult:
        surfaces, _ = expand_scan_surfaces(text)
        best: DetectorResult | None = None
        for surface in surfaces:
            result = await detector.analyze(surface, ctx)
            if best is None or result.score > best.score:
                best = result
        assert best is not None
        return best

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
        surfaces, normalization = expand_scan_surfaces(text)

        async def _score_detector(detector_id: str) -> DetectorResult:
            detector = self._get_detector(detector_id)
            if detector.is_transform:
                return await detector.analyze(text, ctx)
            surface_results = await asyncio.gather(
                *[detector.analyze(surface, ctx) for surface in surfaces]
            )
            best = max(surface_results, key=lambda r: r.score)
            if normalization:
                best.metadata = {
                    **best.metadata,
                    "normalization": ",".join(normalization),
                    "scan_surfaces": str(len(surfaces)),
                }
            return best

        results = list(await asyncio.gather(*[_score_detector(did) for did in ids]))
        return build_verdict(results, request_id=request_id)

    def _get_detector(self, detector_id: str) -> Detector:
        if detector_id not in self._detectors:
            available = ", ".join(sorted(self._detectors))
            raise KeyError(f"Unknown detector {detector_id!r}; available: {available}")
        return self._detectors[detector_id]
