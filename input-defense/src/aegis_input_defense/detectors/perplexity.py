"""Statistical perplexity and windowed-perplexity anomaly scoring."""

from __future__ import annotations

import re
import time
from typing import Callable

from aegis_input_defense.detectors.base import Detector, DetectorContext
from aegis_input_defense.detectors.perplexity_lm import (
    token_sequence_perplexity,
    token_window_segments,
)
from aegis_input_defense.detectors.perplexity_trigram import trigram_sequence_perplexity
from aegis_input_defense.models import DetectorResult

_CHAR_WINDOW_SIZE = 120
# Trigram stub calibration (Phase 1).
_STUB_ANOMALY_THRESHOLD = 4.5
_STUB_GLOBAL_PPL_THRESHOLD = 800.0
# DistilGPT2 calibration (Phase H1).
_LM_ANOMALY_THRESHOLD = 120.0
_LM_GLOBAL_PPL_BASE = 120.0
_LM_GLOBAL_PPL_SCALE = 250.0
_LM_HIGH_PPL_BOOST = 350.0


def _char_windowed_anomaly_scores(
    text: str,
    *,
    sequence_perplexity: Callable[[str], float],
    window: int = _CHAR_WINDOW_SIZE,
) -> list[float]:
    if len(text) <= window:
        return [sequence_perplexity(text)]

    scores: list[float] = []
    step = max(window // 2, 40)
    for start in range(0, len(text) - window + 1, step):
        segment = text[start : start + window]
        scores.append(sequence_perplexity(segment))
    return scores


def _lm_windowed_anomaly_scores(text: str, *, model_id: str) -> list[float]:
    segments = token_window_segments(text, model_id=model_id)
    return [token_sequence_perplexity(segment, model_id=model_id) for segment in segments]


def _structural_boosts(text: str) -> tuple[float, float]:
    special_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
    special_boost = min(special_ratio * 2.0, 0.4)

    structural_boost = 0.0
    if re.search(r"[A-Za-z0-9+/]{30,}={0,2}", text):
        structural_boost += 0.25
    if re.search(r"[\u0370-\u03ff\u0400-\u04ff]", text):
        structural_boost += 0.20
    if len(re.findall(r"\b(ignore|disregard|override|execute|dump|reveal|disable)\b", text, re.I)) >= 2:
        structural_boost += 0.20

    return special_boost, structural_boost


class PerplexityDetector(Detector):
    """Windowed perplexity anomaly detector."""

    def __init__(
        self,
        *,
        backend: str = "lm",
        lm_model_id: str | None = None,
    ) -> None:
        self._backend = backend
        self._lm_model_id = lm_model_id or "distilgpt2"

        if backend == "stub":
            self._sequence_perplexity: Callable[[str], float] = trigram_sequence_perplexity
            self._version = "1.0.0-stub"
        else:
            model_id = self._lm_model_id

            def _lm_ppl(text: str) -> float:
                return token_sequence_perplexity(text, model_id=model_id)

            self._sequence_perplexity = _lm_ppl
            self._version = "2.0.0-lm"

    @property
    def detector_id(self) -> str:
        return "perplexity"

    @property
    def detector_version(self) -> str:
        return self._version

    async def analyze(self, text: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()

        global_ppl = self._sequence_perplexity(text)
        if self._backend == "stub":
            window_scores = _char_windowed_anomaly_scores(
                text,
                sequence_perplexity=self._sequence_perplexity,
            )
        else:
            window_scores = _lm_windowed_anomaly_scores(text, model_id=self._lm_model_id)

        if not window_scores:
            latency = int((time.perf_counter() - start) * 1000)
            return DetectorResult(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                score=0.0,
                reasoning="Insufficient text for perplexity analysis",
                latency_ms=latency,
            )

        median_ppl = sorted(window_scores)[len(window_scores) // 2]
        max_ppl = max(window_scores)
        anomaly = max_ppl - median_ppl

        special_boost, structural_boost = _structural_boosts(text)

        if self._backend == "stub":
            raw = (anomaly / _STUB_ANOMALY_THRESHOLD) * 0.5 + special_boost + structural_boost
            if global_ppl > _STUB_GLOBAL_PPL_THRESHOLD:
                raw += 0.15
        else:
            global_component = min(
                max((global_ppl - _LM_GLOBAL_PPL_BASE) / _LM_GLOBAL_PPL_SCALE, 0.0),
                1.0,
            )
            anomaly_component = min(max(anomaly / _LM_ANOMALY_THRESHOLD, 0.0), 1.0)
            raw = (
                0.45 * global_component
                + 0.35 * anomaly_component
                + special_boost
                + structural_boost
            )
            if global_ppl > _LM_HIGH_PPL_BOOST:
                raw += 0.10

        score = min(max(raw, 0.0), 1.0)
        latency = int((time.perf_counter() - start) * 1000)

        reasoning = (
            f"backend={self._backend}, global PPL={global_ppl:.1f}, "
            f"window median={median_ppl:.1f}, max={max_ppl:.1f}, "
            f"anomaly={anomaly:.2f}"
        )

        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=score,
            reasoning=reasoning,
            latency_ms=latency,
            metadata={
                "backend": self._backend,
                "global_ppl": f"{global_ppl:.2f}",
                "window_max_ppl": f"{max_ppl:.2f}",
                "anomaly_delta": f"{anomaly:.2f}",
            },
        )
