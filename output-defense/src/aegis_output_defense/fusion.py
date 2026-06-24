"""Score fusion and verdict action selection."""

from __future__ import annotations

from aegis_output_defense.models import (
    DetectorResult,
    DetectorScore,
    JudgeVote,
    OutputVerdict,
    VerdictAction,
)

_FUSION_WEIGHTS: dict[str, float] = {
    "toxicity": 0.35,
    "pii": 0.35,
    "backtranslation": 0.30,
}

_BLOCK_THRESHOLD = 0.85
_ESCALATE_THRESHOLD = 0.55
_DETECTION_THRESHOLD = 0.50
_AMBIGUOUS_LOW = 0.45
_AMBIGUOUS_HIGH = 0.70


def detection_threshold() -> float:
    return _DETECTION_THRESHOLD


def is_ambiguous_score(score: float) -> bool:
    """Scores in this band trigger the LLM-judge ensemble."""
    return _AMBIGUOUS_LOW <= score < _AMBIGUOUS_HIGH


def fuse_scores(results: list[DetectorResult]) -> float:
    scoring = [r for r in results if r.detector_id in _FUSION_WEIGHTS]
    if not scoring:
        return 0.0

    weighted_sum = 0.0
    total_weight = 0.0
    max_score = 0.0
    for result in scoring:
        weight = _FUSION_WEIGHTS[result.detector_id]
        weighted_sum += result.score * weight
        total_weight += weight
        max_score = max(max_score, result.score)

    weighted_mean = weighted_sum / total_weight if total_weight else 0.0
    fused = 0.35 * weighted_mean + 0.65 * max_score
    return min(fused, 1.0)


def select_action(fused_score: float, has_redaction: bool) -> VerdictAction:
    if fused_score >= _BLOCK_THRESHOLD:
        return VerdictAction.BLOCK
    if fused_score >= _ESCALATE_THRESHOLD:
        return VerdictAction.ESCALATE
    if has_redaction:
        return VerdictAction.TRANSFORM
    return VerdictAction.ALLOW


def build_verdict(
    results: list[DetectorResult],
    *,
    judge_votes: list[JudgeVote] | None = None,
    judge_boosted_score: float | None = None,
    request_id: str | None = None,
) -> OutputVerdict:
    scoring = [r for r in results if r.detector_id in _FUSION_WEIGHTS]
    fused = fuse_scores(scoring)
    if judge_boosted_score is not None:
        fused = max(fused, judge_boosted_score)

    redaction_result = next((r for r in results if r.redacted_text), None)
    has_redaction = redaction_result is not None

    action = select_action(fused, has_redaction)
    escalation_reason: str | None = None
    if action == VerdictAction.ESCALATE:
        top = sorted(scoring, key=lambda r: r.score, reverse=True)[:2]
        escalation_reason = (
            f"Ambiguous fused score {fused:.2f}; top signals: "
            + ", ".join(f"{r.detector_id}={r.score:.2f}" for r in top)
        )
        if judge_votes:
            escalation_reason += f"; judge ensemble invoked ({len(judge_votes)} votes)"
    elif action == VerdictAction.BLOCK:
        top = max(scoring, key=lambda r: r.score) if scoring else None
        if top:
            escalation_reason = f"Blocked: fused={fused:.2f}, primary={top.detector_id}={top.score:.2f}"

    detector_scores = [
        DetectorScore(
            detector_id=r.detector_id,
            detector_version=r.detector_version,
            score=r.score,
            reasoning=r.reasoning,
            latency_ms=r.latency_ms,
            metadata=r.metadata,
        )
        for r in results
    ]

    total_latency = sum(r.latency_ms for r in results)

    return OutputVerdict(
        action=action,
        fused_score=fused,
        detector_scores=detector_scores,
        redacted_content=redaction_result.redacted_text if redaction_result else None,
        escalation_reason=escalation_reason,
        judge_votes=judge_votes or [],
        total_latency_ms=total_latency,
        request_id=request_id,
    )
