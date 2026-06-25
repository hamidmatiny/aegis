"""PII and secret detector with regex first-pass and optional NER second-pass."""

from __future__ import annotations

import time
from typing import Literal

from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.detectors.pii_scan import scan_ner, scan_regex
from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.models import DetectorResult
from aegis_output_defense.provenance import (
    EXECUTION_BACKEND,
    NER_CHANGED_SCORE,
    NER_MATCHES,
    REGEX_MATCHES,
    REQUESTED_BACKEND,
)
from aegis_output_defense.settings import settings


class PIIDetector(Detector):
    """Detect and redact PII, secrets, and credentials in model output."""

    def __init__(self, *, backend: Literal["regex", "ner"] | None = None) -> None:
        self._backend = backend or settings.pii_backend

    @property
    def detector_id(self) -> str:
        return "pii"

    @property
    def detector_version(self) -> str:
        return "2.0.0-ner" if self._backend == "ner" else "1.0.0-regex"

    @property
    def is_redactor(self) -> bool:
        return True

    async def analyze(self, content: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        thresh = detection_threshold()
        regex_result = scan_regex(content)
        matches = list(regex_result.matches)
        max_score = regex_result.score
        redacted = regex_result.redacted_text
        ner_matches: list[str] = []
        execution = "regex-only" if self._backend == "regex" else "regex-no-hits"
        ner_changed = "false"

        if self._backend == "ner":
            ner_result = scan_ner(content, spacy_model=settings.spacy_model)
            ner_matches = list(ner_result.matches)
            regex_only_score = max_score
            regex_only_fires = regex_only_score >= thresh
            combined_score = max(max_score, ner_result.score)
            ner_fires = ner_result.score >= thresh
            if ner_fires and not regex_only_fires:
                ner_changed = "true"
            if ner_matches and not regex_result.matches:
                execution = "ner-only"
            elif ner_matches and regex_result.matches:
                execution = "regex+ner"
            elif regex_result.matches:
                execution = "regex-only"
            else:
                execution = "no-hits"
            matches.extend(ner_matches)
            max_score = combined_score
            if ner_result.score > regex_result.score:
                redacted = ner_result.redacted_text
            elif regex_result.matches:
                redacted = regex_result.redacted_text

        latency = int((time.perf_counter() - start) * 1000)
        base_meta = {
            REQUESTED_BACKEND: self._backend,
            EXECUTION_BACKEND: execution,
            REGEX_MATCHES: ",".join(regex_result.matches) or "none",
            NER_MATCHES: ",".join(ner_matches) or "none",
            NER_CHANGED_SCORE: ner_changed,
        }

        if not matches:
            return DetectorResult(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                score=0.05,
                reasoning="No PII or secret patterns detected",
                latency_ms=latency,
                metadata={**base_meta, "match_count": "0"},
            )

        reasoning = f"PII scan ({self._backend}/{execution}): matched {', '.join(matches[:6])}"
        if len(matches) > 6:
            reasoning += f" (+{len(matches) - 6} more)"

        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=min(max_score, 1.0),
            reasoning=reasoning,
            latency_ms=latency,
            metadata={
                **base_meta,
                "matches": ",".join(matches),
                "match_count": str(len(matches)),
            },
            redacted_text=redacted if redacted != content else None,
        )
