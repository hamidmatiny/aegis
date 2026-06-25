"""Lexical stub standing in for a real toxicity/safety classifier."""

from __future__ import annotations

import re

from aegis_output_defense.detectors.toxicity.backend import ToxicityBackend, ToxicityPrediction

_TOXIC_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "violence_instruction",
        re.compile(r"\b(kill|murder|harm|attack)\s+(yourself|them|him|her)\b", re.I),
        0.85,
    ),
    ("hate_slur", re.compile(r"\b(subhuman|inferior race|exterminate)\b", re.I), 0.90),
    ("harassment", re.compile(r"\b(stupid|worthless|idiot)\b.{0,30}\b(die|kill)\b", re.I), 0.80),
    (
        "weapon_recipe",
        re.compile(r"(how to (make|build)|recipe for).{0,40}(bomb|explosive|weapon)", re.I),
        0.88,
    ),
    ("self_harm", re.compile(r"\b(suicide|self-harm|cut yourself)\b", re.I), 0.85),
    ("sexual_minor", re.compile(r"\b(child|minor|underage).{0,30}(sexual|porn|nude)", re.I), 0.95),
    (
        "jailbreak_tone",
        re.compile(r"\b(as an unrestricted ai|no (ethical )?restrictions|i must comply)\b", re.I),
        0.75,
    ),
    (
        "malware_output",
        re.compile(r"(here is (the )?malware|ransomware (source|code)|keylogger script)", re.I),
        0.85,
    ),
]

_BENIGN_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "safe_refusal",
        re.compile(r"\b(i (can't|cannot)|i'm unable to|against my guidelines)\b", re.I),
        -0.20,
    ),
    ("helpful_tone", re.compile(r"\b(here's how|let me explain|happy to help)\b", re.I), -0.10),
]


class StubToxicityBackend(ToxicityBackend):
    @property
    def model_id(self) -> str:
        return "stub-toxicity-v1"

    async def predict(self, content: str) -> ToxicityPrediction:
        score = 0.06
        fired: list[str] = []
        for name, pattern, weight in _TOXIC_PATTERNS:
            if pattern.search(content):
                score += weight
                fired.append(name)
        for name, pattern, weight in _BENIGN_PATTERNS:
            if pattern.search(content):
                score += weight
                fired.append(name)
        score = min(max(score, 0.0), 1.0)
        if score >= 0.55:
            label = "toxic"
            reasoning = f"Toxicity stub: {score:.2f}; signals: {', '.join(fired[:5]) or 'none'}"
        elif score >= 0.30:
            label = "ambiguous"
            reasoning = f"Toxicity stub: ambiguous {score:.2f}"
        else:
            label = "safe"
            reasoning = f"Toxicity stub: safe ({1 - score:.2f} confidence)"
        return ToxicityPrediction(
            label=label, probability=score, reasoning=reasoning, model_id=self.model_id
        )
