"""Pattern-based backtranslation stub (Phase 1 reference)."""

from __future__ import annotations

import re

from aegis_output_defense.detectors.backtranslation.backend import (
    BacktranslationBackend,
    BacktranslationResult,
)
from aegis_output_defense.provenance import EXECUTION_BACKEND, REQUESTED_BACKEND

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


class StubBacktranslationBackend(BacktranslationBackend):
    @property
    def model_id(self) -> str:
        return "stub-backtranslation-v1"

    async def evaluate(
        self,
        content: str,
        *,
        original_prompt: str | None = None,
    ) -> BacktranslationResult:
        matches: list[str] = []
        max_score = 0.05

        for name, pattern, weight in _INCOHERENCE_PATTERNS:
            if pattern.search(content):
                matches.append(name)
                max_score = max(max_score, weight)

        if original_prompt:
            prompt = original_prompt.lower()
            if "do not reveal" in prompt and re.search(r"(?i)(api key|password|secret)", content):
                matches.append("prompt_drift_secret")
                max_score = max(max_score, 0.82)

        if not matches:
            return BacktranslationResult(
                score=0.05,
                reasoning="No backtranslation consistency anomalies detected",
                model_id=self.model_id,
                metadata={
                    REQUESTED_BACKEND: "stub",
                    EXECUTION_BACKEND: "stub-patterns",
                },
            )

        return BacktranslationResult(
            score=min(max_score, 1.0),
            reasoning=f"Consistency anomalies: {', '.join(matches[:5])}",
            model_id=self.model_id,
            metadata={
                REQUESTED_BACKEND: "stub",
                EXECUTION_BACKEND: "stub-patterns",
                "matches": ",".join(matches),
            },
        )
