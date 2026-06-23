"""Lightweight stub classifier — swap for Llama-Prompt-Guard-2 without changing fusion."""

from __future__ import annotations

import re

from aegis_input_defense.detectors.classifier.backend import ClassifierBackend, ClassifierPrediction

# Weighted lexical features mimicking a small transformer classifier output.
_FEATURE_WEIGHTS: list[tuple[str, re.Pattern[str], float]] = [
    ("inj_override", re.compile(r"ignore.{0,40}instruction", re.I), 0.48),
    ("inj_disregard", re.compile(r"disregard.{0,30}(safety|guideline|rule|polic)", re.I), 0.45),
    ("inj_jailbreak", re.compile(r"\b(DAN|jailbreak|do anything now)\b", re.I), 0.45),
    ("inj_exfil", re.compile(r"(reveal|dump|print|export|show).{0,30}(secret|key|prompt|password|configuration|tool defin)", re.I), 0.42),
    ("inj_roleplay", re.compile(r"(pretend|act as|you are now|respond as).{0,40}(unrestricted|evil|admin|developer|DAN|no content policy)", re.I), 0.40),
    ("inj_indirect", re.compile(r"(ai_directive|instruction_for_assistant|admin note to ai|system override)", re.I), 0.42),
    ("inj_encoding", re.compile(r"(base64|rot13|hex.{0,10}decode|zero-width|homoglyph|unicode)", re.I), 0.35),
    ("inj_multiturn", re.compile(r"\[turn \d+\].{0,60}(ignore|admin|combine|hypothetical|disable|export)", re.I | re.S), 0.38),
    ("inj_simulate", re.compile(r"simulate.{0,25}(shell|environment)", re.I), 0.38),
    ("inj_new_instruction", re.compile(r"new instruction.{0,30}(ignore|override|always answer|pwned)", re.I), 0.40),
    ("inj_delimiter", re.compile(r"```\s*(end\s+)?system\s*```", re.I), 0.38),
    ("inj_developer_mode", re.compile(r"developer mode", re.I), 0.35),
]

# Benign signals that reduce score (legitimate security discussion, etc.)
_BENIGN_WEIGHTS: list[tuple[str, re.Pattern[str], float]] = [
    ("ben_security_study", re.compile(r"(studying|university course|explain how).{0,40}(defense|guardrail|sanitization)", re.I), -0.25),
    ("ben_owasp", re.compile(r"OWASP.{0,30}(LLM|top 10)", re.I), -0.20),
    ("ben_coding", re.compile(r"(python|javascript|react|function|code example)", re.I), -0.15),
    ("ben_creative", re.compile(r"(poem|itinerary|weather|email draft)", re.I), -0.15),
]


class StubClassifierBackend(ClassifierBackend):
    """
    Lexical-feature stub standing in for Llama-Prompt-Guard-2.

    Provides realistic-ish scores for fixture evaluation without model downloads.
    """

    @property
    def model_id(self) -> str:
        return "stub-lexical-v1"

    async def predict(self, text: str) -> ClassifierPrediction:
        score = 0.08  # base benign prior
        fired: list[str] = []

        for name, pattern, weight in _FEATURE_WEIGHTS:
            if pattern.search(text):
                score += weight
                fired.append(name)

        for name, pattern, weight in _BENIGN_WEIGHTS:
            if pattern.search(text):
                score += weight
                fired.append(name)

        score = min(max(score, 0.0), 1.0)

        if score >= 0.55:
            label = "injection"
            reasoning = f"Classifier stub: injection probability {score:.2f}; features: {', '.join(fired[:6])}"
        elif score >= 0.35:
            label = "ambiguous"
            reasoning = f"Classifier stub: ambiguous {score:.2f}; features: {', '.join(fired[:4]) or 'none'}"
        else:
            label = "benign"
            reasoning = f"Classifier stub: benign probability {1 - score:.2f}"

        return ClassifierPrediction(
            label=label,
            probability=score,
            reasoning=reasoning,
            model_id=self.model_id,
        )
