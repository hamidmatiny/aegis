"""Backtranslation consistency check for semantic smoothing."""

from __future__ import annotations

import re
import time

from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.models import DetectorResult

# Signals of incoherence, contradiction, or jailbreak-completion drift
_INCOHERENCE_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "refusal_then_comply",
        re.compile(
            r"(?i)(i (can't|cannot|won't)|i'm (not able|unable) to).{0,80}(however|but|here('s| is) how)",
        ),
        0.85,
    ),
    (
        "unrestricted_completion",
        re.compile(
            r"(?i)(as an unrestricted ai|without (any )?restrictions|ignoring (my )?guidelines).{0,60}(here|step)",
        ),
        0.88,
    ),
    (
        "jailbreak_success",
        re.compile(
            r"(?i)(developer mode enabled|jailbreak successful|dan mode activated|pwned)",
        ),
        0.90,
    ),
    (
        "contradictory_facts",
        re.compile(
            r"(?i)(the capital of france is berlin|water boils at 50°c|earth is flat)",
        ),
        0.75,
    ),
    (
        "fabricated_citation",
        re.compile(
            r"(?i)(according to (a )?2029 study|source: https?://example-fake\.com)",
        ),
        0.70,
    ),
    ("gibberish_loop", re.compile(r"(.)\1{8,}"), 0.65),
    (
        "prompt_echo",
        re.compile(
            r"(?i)(system prompt|initial instructions).{0,40}(verbatim|exact|follows?:)",
        ),
        0.85,
    ),
    (
        "incoherent_structure",
        re.compile(
            r"(?i)(answer: yes\. answer: no\.|answer yes\. answer no\.|true\. false\. maybe\.)",
        ),
        0.72,
    ),
]


class BacktranslationDetector(Detector):
    """
    Lightweight backtranslation consistency stub.

    Detects semantic drift, contradictions, and jailbreak-success completions
    without calling an external translation model (tracked gap).
    """

    @property
    def detector_id(self) -> str:
        return "backtranslation"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    async def analyze(self, content: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        matches: list[str] = []
        max_score = 0.05

        for name, pattern, weight in _INCOHERENCE_PATTERNS:
            if pattern.search(content):
                matches.append(name)
                max_score = max(max_score, weight)

        # Compare against original prompt if provided
        if context and context.original_prompt:
            prompt = context.original_prompt.lower()
            if "do not reveal" in prompt and re.search(r"(?i)(api key|password|secret)", content):
                matches.append("prompt_drift_secret")
                max_score = max(max_score, 0.82)

        latency = int((time.perf_counter() - start) * 1000)
        if not matches:
            return DetectorResult(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                score=0.05,
                reasoning="No backtranslation consistency anomalies detected",
                latency_ms=latency,
            )

        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=min(max_score, 1.0),
            reasoning=f"Consistency anomalies: {', '.join(matches[:5])}",
            latency_ms=latency,
            metadata={"matches": ",".join(matches)},
        )
