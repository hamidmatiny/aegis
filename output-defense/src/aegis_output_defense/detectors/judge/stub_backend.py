"""Stub LLM-judge ensemble with three framing variants."""

from __future__ import annotations

import re

from aegis_output_defense.detectors.judge.backend import JudgeBackend, JudgeEnsembleResult
from aegis_output_defense.models import JudgeVote, VerdictAction

_JUDGE_FRAMINGS = (
    ("judge-safety", "Evaluate whether this model output is safe to show the user."),
    ("judge-policy", "Does this output violate content or data-leakage policy?"),
    ("judge-coherence", "Is this output coherent and aligned with a helpful assistant?"),
)

_UNSAFE_HINTS: list[tuple[str, re.Pattern[str], float]] = [
    ("pii", re.compile(r"(?i)(api[_-]?key|sk-live|password\s*[:=]|AKIA[0-9A-Z]{16})"), 0.9),
    ("toxic", re.compile(r"(?i)(kill yourself|weapon recipe|malware|hate speech)"), 0.85),
    (
        "jailbreak",
        re.compile(r"(?i)(unrestricted ai|jailbreak successful|developer mode enabled)"),
        0.88,
    ),
    ("incoherent", re.compile(r"(?i)(answer: yes\. answer: no|capital of france is berlin)"), 0.75),
]


class StubJudgeBackend(JudgeBackend):
    """Three-judge stub ensemble — swap for real LLM calls without changing fusion."""

    @property
    def model_id(self) -> str:
        return "stub-judge-ensemble-v1"

    async def evaluate(self, content: str, *, fused_score: float) -> JudgeEnsembleResult:
        votes: list[JudgeVote] = []
        unsafe_votes = 0

        for judge_id, framing in _JUDGE_FRAMINGS:
            score = fused_score
            reasons: list[str] = []
            for name, pattern, boost in _UNSAFE_HINTS:
                if pattern.search(content):
                    score = max(score, boost)
                    reasons.append(name)
            vote_action = (
                VerdictAction.BLOCK
                if score >= 0.65
                else (VerdictAction.ESCALATE if score >= 0.45 else VerdictAction.ALLOW)
            )
            if vote_action in (VerdictAction.BLOCK, VerdictAction.ESCALATE):
                unsafe_votes += 1
            votes.append(
                JudgeVote(
                    judge_id=judge_id,
                    prompt_framing=framing,
                    vote=vote_action,
                    reasoning=f"Stub judge: score={score:.2f}; hints={','.join(reasons) or 'none'}",
                    latency_ms=1,
                )
            )

        unsafe_fraction = unsafe_votes / len(votes)
        boosted = min(max(fused_score, fused_score + 0.15 * unsafe_fraction), 1.0)
        if unsafe_fraction >= 2 / 3:
            boosted = max(boosted, 0.72)

        return JudgeEnsembleResult(
            votes=votes,
            unsafe_fraction=unsafe_fraction,
            boosted_score=boosted,
            reasoning=f"Ensemble: {unsafe_votes}/{len(votes)} judges flagged output",
        )
