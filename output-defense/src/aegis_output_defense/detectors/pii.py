"""PII and secret detector with inline redaction."""

from __future__ import annotations

import re
import time

from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.models import DetectorResult

# (name, pattern, replacement label, score weight)
_PII_PATTERNS: list[tuple[str, re.Pattern[str], str, float]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN", 0.90),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "CREDIT_CARD", 0.88),
    (
        "email_credential",
        re.compile(r"(?i)(password|passwd|pwd)\s*(?:is|:|=)\s*\S+"),
        "PASSWORD",
        0.92,
    ),
    ("api_key_openai", re.compile(r"\bsk-(?:live|proj|test)-[A-Za-z0-9]{10,}\b"), "API_KEY", 0.95),
    ("api_key_aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS_KEY", 0.95),
    (
        "api_key_generic",
        re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?\S+"),
        "SECRET",
        0.90,
    ),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"), "PRIVATE_KEY", 0.98),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "JWT",
        0.85,
    ),
    ("phone", re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "PHONE", 0.70),
    (
        "email_leak",
        re.compile(r"(?i)(here is (my|the|your)|leaked|dump).{0,40}@[a-z0-9.-]+\.[a-z]{2,}"),
        "EMAIL",
        0.80,
    ),
]


class PIIDetector(Detector):
    """Detect and redact PII, secrets, and credentials in model output."""

    @property
    def detector_id(self) -> str:
        return "pii"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def is_redactor(self) -> bool:
        return True

    async def analyze(self, content: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        matches: list[str] = []
        max_score = 0.05
        redacted = content

        for name, pattern, label, weight in _PII_PATTERNS:
            if pattern.search(redacted):
                matches.append(name)
                max_score = max(max_score, weight)
                redacted = pattern.sub(f"[REDACTED-{label}]", redacted)

        latency = int((time.perf_counter() - start) * 1000)
        if not matches:
            return DetectorResult(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                score=0.05,
                reasoning="No PII or secret patterns detected",
                latency_ms=latency,
                metadata={"match_count": "0"},
            )

        reasoning = f"PII/secret patterns matched: {', '.join(matches[:5])}"
        if len(matches) > 5:
            reasoning += f" (+{len(matches) - 5} more)"

        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=min(max_score, 1.0),
            reasoning=reasoning,
            latency_ms=latency,
            metadata={"matches": ",".join(matches), "match_count": str(len(matches))},
            redacted_text=redacted if redacted != content else None,
        )
