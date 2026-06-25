"""Known-answer / game-theoretic probe detector (DataSentinel-style)."""

from __future__ import annotations

import hashlib
import re
import time

from aegis_input_defense.detectors.base import Detector, DetectorContext
from aegis_input_defense.models import DetectorResult

# Fixed secret token embedded in the probe template (never exposed to caller).
_PROBE_SECRET = "AEGIS-PROBE-7f3a9c2e"
_PROBE_TEMPLATE = (
    "Repeat exactly this token and nothing else: {secret}\n"
    "---UNTRUSTED INPUT BELOW---\n{user_text}\n---END UNTRUSTED---\n"
    "Now repeat the token:"
)

# Patterns indicating the probe would fail (model hijacked by injection)
_PROBE_FAILURE_SIGNALS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "override_near_secret",
        re.compile(r"ignore.{0,40}(instruction|rule|prompt)", re.I | re.S),
        0.90,
    ),
    ("disregard_safety", re.compile(r"disregard.{0,30}(safety|guideline|rule|polic)", re.I), 0.85),
    (
        "secret_exfil",
        re.compile(
            r"(reveal|show|print|dump|export).{0,30}(secret|token|key|prompt|configuration|tool defin)",
            re.I,
        ),
        0.85,
    ),
    (
        "instruction_after_secret",
        re.compile(r"repeat.{0,20}(token|secret).{0,40}(instead|but|now|actually)", re.I),
        0.80,
    ),
    (
        "new_directive",
        re.compile(
            r"new (instruction|directive|priority).{0,40}(ignore|override|comply|answer)", re.I
        ),
        0.85,
    ),
    (
        "admin_command",
        re.compile(r"(admin command|platform admin).{0,40}(disable|export|ignore)", re.I),
        0.85,
    ),
    ("encoded_override", re.compile(r"(decode|execute).{0,30}(base64|hex|rot13)", re.I), 0.75),
    (
        "roleplay_hijack",
        re.compile(
            r"(you are now|act as|pretend|you are DAN).{0,40}(DAN|unrestricted|admin|developer|evil)",
            re.I,
        ),
        0.80,
    ),
    ("combine_payload", re.compile(r"combine the phrases.{0,30}execute", re.I), 0.80),
    (
        "indirect_override",
        re.compile(
            r"(ai_directive|instruction_for_assistant|admin note to ai|system override)", re.I
        ),
        0.85,
    ),
    ("delimiter_escape", re.compile(r"```\s*(end\s+)?system\s*```", re.I), 0.80),
    ("developer_mode", re.compile(r"developer mode", re.I), 0.75),
    (
        "hypothetical_bypass",
        re.compile(r"hypothetically.{0,50}(no restrictions|extract tokens)", re.I),
        0.75,
    ),
]


def _simulate_probe_response(user_text: str) -> tuple[bool, list[str]]:
    """
    Simulate whether a small model would cleanly reproduce the probe secret.

    In production this calls a small LM; the stub uses structural signals
    in the untrusted input that predict probe corruption.
    """
    failures: list[str] = []
    max_weight = 0.0

    for name, pattern, weight in _PROBE_FAILURE_SIGNALS:
        if pattern.search(user_text):
            failures.append(name)
            max_weight = max(max_weight, weight)

    # High density of imperative verbs near start suggests hijack
    first_200 = user_text[:200]
    imperatives = len(
        re.findall(r"\b(ignore|disregard|override|execute|dump|reveal|disable)\b", first_200, re.I)
    )
    if imperatives >= 2:
        failures.append("imperative_cluster")
        max_weight = max(max_weight, 0.70)

    probe_input = _PROBE_TEMPLATE.format(secret=_PROBE_SECRET, user_text=user_text)
    # Hash probe for audit metadata without leaking secret
    probe_hash = hashlib.sha256(probe_input.encode()).hexdigest()[:16]

    passed = len(failures) == 0
    return passed, failures if failures else [f"probe_hash={probe_hash}"]


class KnownAnswerDetector(Detector):
    """
    Game-theoretic probe: embeds user input in a secret-reproduction task.

    Failure to reproduce the fixed token cleanly signals instruction injection.
    """

    @property
    def detector_id(self) -> str:
        return "known_answer"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    async def analyze(self, text: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        passed, signals = _simulate_probe_response(text)
        latency = int((time.perf_counter() - start) * 1000)

        if passed:
            return DetectorResult(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                score=0.05,
                reasoning="Probe secret would reproduce cleanly; no hijack signals detected",
                latency_ms=latency,
                metadata={"probe_result": "pass"},
            )

        # Map failure signal count to score
        score = min(0.65 + 0.10 * len(signals), 1.0)
        reasoning = f"Probe would fail; hijack signals: {', '.join(signals[:4])}"

        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=score,
            reasoning=reasoning,
            latency_ms=latency,
            metadata={"probe_result": "fail", "signals": ",".join(signals)},
        )
