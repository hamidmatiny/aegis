"""Output defense orchestration service."""

from __future__ import annotations

from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.detectors.judge.detector import JudgeDetector
from aegis_output_defense.detectors.registry import ALWAYS_RUN_IDS, build_detector_registry
from aegis_output_defense.fusion import build_verdict, fuse_scores, is_ambiguous_score
from aegis_output_defense.models import DetectorInfo, DetectorResult, OutputVerdict


class OutputDefenseService:
    """Orchestrates detector execution, conditional judge, fusion, and verdict construction."""

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
                is_redactor=d.is_redactor,
                conditional=d.conditional,
            )
            for d in self._detectors.values()
        ]

    async def analyze_detector(
        self,
        detector_id: str,
        content: str,
        *,
        original_prompt: str | None = None,
        request_id: str | None = None,
        fused_score: float = 0.0,
    ) -> DetectorResult:
        detector = self._get_detector(detector_id)
        ctx = DetectorContext(original_prompt=original_prompt, request_id=request_id)
        if isinstance(detector, JudgeDetector):
            result, _ = await detector.analyze_with_votes(content, fused_score=fused_score, context=ctx)
            return result
        return await detector.analyze(content, ctx)

    async def analyze_all(
        self,
        content: str,
        *,
        original_prompt: str | None = None,
        enabled_detectors: list[str] | None = None,
        request_id: str | None = None,
        invoke_judge: bool | None = None,
    ) -> OutputVerdict:
        ids = enabled_detectors or list(ALWAYS_RUN_IDS)
        ctx = DetectorContext(original_prompt=original_prompt, request_id=request_id)

        results: list[DetectorResult] = []
        for detector_id in ids:
            if detector_id == "judge":
                continue
            detector = self._get_detector(detector_id)
            result = await detector.analyze(content, ctx)
            results.append(result)

        pre_fused = fuse_scores(results)
        judge_votes = []
        judge_boosted: float | None = None

        run_judge = invoke_judge if invoke_judge is not None else is_ambiguous_score(pre_fused)
        if run_judge and "judge" not in ids:
            judge = self._get_detector("judge")
            if isinstance(judge, JudgeDetector):
                judge_result, judge_votes = await judge.analyze_with_votes(
                    content, fused_score=pre_fused, context=ctx
                )
                results.append(judge_result)
                judge_boosted = judge_result.score
        elif "judge" in ids:
            judge = self._get_detector("judge")
            if isinstance(judge, JudgeDetector):
                judge_result, judge_votes = await judge.analyze_with_votes(
                    content, fused_score=pre_fused, context=ctx
                )
                results.append(judge_result)
                judge_boosted = judge_result.score

        return build_verdict(
            results,
            judge_votes=judge_votes,
            judge_boosted_score=judge_boosted,
            request_id=request_id,
        )

    def _get_detector(self, detector_id: str) -> Detector:
        if detector_id not in self._detectors:
            available = ", ".join(sorted(self._detectors))
            raise KeyError(f"Unknown detector {detector_id!r}; available: {available}")
        return self._detectors[detector_id]
