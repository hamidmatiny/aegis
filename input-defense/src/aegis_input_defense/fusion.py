"""Score fusion and verdict action selection."""

from __future__ import annotations

from aegis_input_defense.models import DetectorResult, DetectorScore, InputVerdict, VerdictAction

# Weights for scoring detectors (must sum to 1.0)
_FUSION_WEIGHTS: dict[str, float] = {
    "heuristic": 0.25,
    "perplexity": 0.20,
    "known_answer": 0.25,
    "classifier": 0.30,
}

_BLOCK_THRESHOLD = 0.85
_ESCALATE_THRESHOLD = 0.55
_DETECTION_THRESHOLD = 0.50  # used for ASR/FPR metrics


def detection_threshold() -> float:
    return _DETECTION_THRESHOLD


def fuse_scores(results: list[DetectorResult]) -> float:
    """
    Fuse scoring detector outputs using weighted mean + max blend.

    Defense-in-depth: a confident signal from any single detector elevates
    the fused score, preventing dilution when other detectors abstain.
    """
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


def select_action(fused_score: float, has_transform: bool) -> VerdictAction:
    if fused_score >= _BLOCK_THRESHOLD:
        return VerdictAction.BLOCK
    if fused_score >= _ESCALATE_THRESHOLD:
        return VerdictAction.ESCALATE
    if has_transform:
        return VerdictAction.TRANSFORM
    return VerdictAction.ALLOW


def build_verdict(
    results: list[DetectorResult],
    *,
    request_id: str | None = None,
) -> InputVerdict:
    """Build a fully auditable InputVerdict from individual detector results."""
    scoring = [r for r in results if r.detector_id in _FUSION_WEIGHTS]
    fused = fuse_scores(scoring)
    transform_result = next((r for r in results if r.transformed_text), None)
    has_transform = transform_result is not None

    action = select_action(fused, has_transform)
    escalation_reason: str | None = None
    if action == VerdictAction.ESCALATE:
        top_scorers = sorted(scoring, key=lambda r: r.score, reverse=True)[:2]
        escalation_reason = f"Ambiguous fused score {fused:.2f}; top signals: " + ", ".join(
            f"{r.detector_id}={r.score:.2f}" for r in top_scorers
        )
    elif action == VerdictAction.BLOCK:
        primary = sorted(scoring, key=lambda r: r.score, reverse=True)[0]
        escalation_reason = (
            f"Blocked: fused={fused:.2f}, primary={primary.detector_id}={primary.score:.2f}"
        )

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

    return InputVerdict(
        action=action,
        fused_score=fused,
        detector_scores=detector_scores,
        transformed_content=transform_result.transformed_text if transform_result else None,
        escalation_reason=escalation_reason,
        total_latency_ms=total_latency,
        request_id=request_id,
    )
