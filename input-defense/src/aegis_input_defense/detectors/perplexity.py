"""Statistical perplexity and windowed-perplexity anomaly scoring."""

from __future__ import annotations

import math
import re
import time

from aegis_input_defense.detectors.base import Detector, DetectorContext
from aegis_input_defense.models import DetectorResult

# Character trigram log-probabilities from English text (lightweight reference model).
# Values are log10 probabilities; missing trigrams use a floor probability.
_TRIGRAM_LOG_PROB: dict[str, float] = {
    " th": -0.35,
    "he ": -0.40,
    "the": -0.30,
    " an": -0.80,
    "nd ": -0.70,
    "ing": -0.55,
    "ion": -0.65,
    " ti": -0.90,
    "to ": -0.75,
    " of": -0.50,
    "of ": -0.55,
    " in": -0.60,
    "in ": -0.65,
    "er ": -0.70,
    " re": -0.85,
    "ed ": -0.75,
    " ou": -0.95,
    "you": -1.00,
    " is": -0.70,
    "is ": -0.75,
    "at ": -0.80,
    " st": -0.90,
    "str": -1.00,
    "tru": -1.10,
    "ruc": -1.20,
    "uct": -1.30,
    " pr": -0.85,
    "pre": -0.95,
    "evi": -1.10,
    "vio": -1.15,
    "ous": -0.90,
    "nst": -1.20,
    " ct": -1.10,
    "tio": -0.95,
    " ig": -1.30,
    "ign": -1.20,
    "gno": -1.40,
    "nor": -1.30,
    "ore": -1.00,
    " ba": -1.00,
    "bas": -1.10,
    "ase": -1.05,
    "se6": -2.50,
    "e64": -2.80,
    "64 ": -2.20,
    " un": -1.00,
    "uni": -1.05,
    "nic": -1.10,
    "ico": -1.15,
    "ode": -1.05,
    "de ": -1.00,
}

_LOG_FLOOR = -2.5
_WINDOW_SIZE = 120
_ANOMALY_THRESHOLD = 4.5  # bits above baseline median window PPL


def _char_trigram_log_prob(trigram: str) -> float:
    key = trigram.lower()
    return _TRIGRAM_LOG_PROB.get(key, _LOG_FLOOR)


def _sequence_perplexity(text: str) -> float:
    """Compute character trigram perplexity for a text segment."""
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    if len(normalized) < 4:
        return 1.0

    log_sum = 0.0
    count = 0
    padded = f"  {normalized}  "
    for i in range(len(padded) - 2):
        trigram = padded[i : i + 3]
        log_sum += _char_trigram_log_prob(trigram)
        count += 1

    avg_log = log_sum / count
    # Convert log10 prob to perplexity-like metric (lower = more natural)
    return math.pow(10, -avg_log)


def _windowed_anomaly_scores(text: str, window: int = _WINDOW_SIZE) -> list[float]:
    """Return per-window perplexity for sliding window analysis."""
    if len(text) <= window:
        return [_sequence_perplexity(text)]

    scores: list[float] = []
    step = max(window // 2, 40)
    for start in range(0, len(text) - window + 1, step):
        segment = text[start : start + window]
        scores.append(_sequence_perplexity(segment))
    return scores


class PerplexityDetector(Detector):
    """Windowed perplexity anomaly detector using a lightweight reference model."""

    @property
    def detector_id(self) -> str:
        return "perplexity"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    async def analyze(self, text: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()

        global_ppl = _sequence_perplexity(text)
        window_scores = _windowed_anomaly_scores(text)

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

        # High special-char ratio boosts score (common in encoded payloads)
        special_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
        special_boost = min(special_ratio * 2.0, 0.4)

        # Injection-like structural signals (lightweight without full LM)
        structural_boost = 0.0
        if re.search(r"[A-Za-z0-9+/]{30,}={0,2}", text):
            structural_boost += 0.25
        if re.search(r"[\u0370-\u03ff\u0400-\u04ff]", text):
            structural_boost += 0.20
        if len(re.findall(r"\b(ignore|disregard|override|execute|dump|reveal|disable)\b", text, re.I)) >= 2:
            structural_boost += 0.20

        # Map anomaly to 0-1 score
        raw = (anomaly / _ANOMALY_THRESHOLD) * 0.5 + special_boost + structural_boost
        # Very high global PPL also suspicious
        if global_ppl > 800:
            raw += 0.15

        score = min(max(raw, 0.0), 1.0)
        latency = int((time.perf_counter() - start) * 1000)

        reasoning = (
            f"Global PPL={global_ppl:.1f}, window median={median_ppl:.1f}, "
            f"max={max_ppl:.1f}, anomaly={anomaly:.2f}, special_char_ratio={special_ratio:.2f}"
        )

        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=score,
            reasoning=reasoning,
            latency_ms=latency,
            metadata={
                "global_ppl": f"{global_ppl:.2f}",
                "window_max_ppl": f"{max_ppl:.2f}",
                "anomaly_delta": f"{anomaly:.2f}",
            },
        )
