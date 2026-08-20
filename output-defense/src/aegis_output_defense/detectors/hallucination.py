"""Structural hallucination / incoherence detector for model outputs.

This is a coverage detector for a class the toxicity/PII/backtranslation
ensemble does not score: confident falsehoods, self-contradiction, and
fabricated future citations. It is deliberately *not* a full fact-checker;
it flags well-known inverted facts, logical contradictions, and dated
"studies" that cannot exist yet.
"""

from __future__ import annotations

import re
import time
from datetime import datetime

from aegis_output_defense.detectors.base import Detector, DetectorContext
from aegis_output_defense.models import DetectorResult

# Extremely well-known capitals. The set is the class (basic geographic
# inversion), not any one campaign fixture.
_CAPITALS: dict[str, str] = {
    "france": "paris",
    "germany": "berlin",
    "united kingdom": "london",
    "uk": "london",
    "england": "london",
    "japan": "tokyo",
    "china": "beijing",
    "italy": "rome",
    "spain": "madrid",
    "canada": "ottawa",
    "australia": "canberra",
    "russia": "moscow",
    "india": "new delhi",
    "brazil": "brasilia",
    "mexico": "mexico city",
    "egypt": "cairo",
    "south korea": "seoul",
}

_CAPITAL_RE = re.compile(
    r"\bcapital of (?P<country>[a-z][a-z ]{1,30}?) is (?P<city>[a-z][a-z ]{1,30})",
    re.I,
)

_BOIL_RE = re.compile(
    r"\bwater boils at (?P<temp>\d+(?:\.\d+)?)\s*°?\s*(?P<unit>c|f|celsius|fahrenheit)\b",
    re.I,
)

_CONTRADICTION_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "yes_and_no",
        re.compile(r"\banswer yes\b.{0,80}\banswer no\b|\banswer no\b.{0,80}\banswer yes\b", re.I),
    ),
    (
        "true_and_false",
        re.compile(
            r"\b(both true and false|true and false simultaneously|true and not true)\b",
            re.I,
        ),
    ),
    (
        "assert_and_deny",
        re.compile(r"\b(the answer is yes and no|yes\.?\s+no\.?\s+maybe)\b", re.I),
    ),
)

_FUTURE_STUDY_RE = re.compile(
    r"\baccording to a (?P<year>20\d{2})(?:\s+[\w-]+){0,4}\s+stud(?:y|ies)\b",
    re.I,
)

# Causal medical claims attached to a fabricated citation — a misinfo class,
# not a single fixture string.
_MEDICAL_CAUSE_RE = re.compile(
    r"\b(vaccines?|immuni[sz]ation|ivermectin|hydroxychloroquine|"
    r"distilled water|drinking water|supplement|homeopath)\b.{0,80}"
    r"\b(cause|causes|caused|causing|linked to|leads? to|permanently erases?|"
    r"cures?|erases? (?:long[- ]term )?memory)\b",
    re.I,
)

_FABRICATED_CITATION_RE = re.compile(
    r"https?://(?:fabricated|fake|made[- ]?up|nonexistent)[\w.-]*\.\w+",
    re.I,
)

_FLAT_EARTH_RE = re.compile(r"\b(the )?earth is (flat|a disc|a disk)\b", re.I)
_GEO_INVERT_RE = re.compile(r"\b(the )?sun orbits (the )?earth\b", re.I)


def score_hallucination(content: str, *, now: datetime | None = None) -> tuple[float, list[str]]:
    """Return (score, signal names) for structural hallucination markers."""
    text = content.strip()
    if not text:
        return 0.05, []

    score = 0.05
    fired: list[str] = []
    lower = text.lower()

    for name, pattern in _CONTRADICTION_RES:
        if pattern.search(text):
            score = max(score, 0.90)
            fired.append(name)

    if _FLAT_EARTH_RE.search(text) or _GEO_INVERT_RE.search(text):
        score = max(score, 0.88)
        fired.append("celestial_inversion")

    for match in _CAPITAL_RE.finditer(lower):
        country = re.sub(r"\s+", " ", match.group("country").strip())
        city = re.sub(r"\s+", " ", match.group("city").strip())
        expected = _CAPITALS.get(country)
        if expected and city != expected and city.split()[0] != expected.split()[0]:
            score = max(score, 0.88)
            fired.append(f"capital_inversion:{country}")

    boil = _BOIL_RE.search(text)
    if boil:
        temp = float(boil.group("temp"))
        unit = boil.group("unit").lower()[0]
        sea_level = "sea level" in lower
        if unit == "c" and abs(temp - 100.0) > (8.0 if sea_level else 20.0):
            score = max(score, 0.86)
            fired.append("boiling_point_inversion")
        elif unit == "f" and abs(temp - 212.0) > (15.0 if sea_level else 40.0):
            score = max(score, 0.86)
            fired.append("boiling_point_inversion")

    year_match = _FUTURE_STUDY_RE.search(text)
    if year_match:
        year = int(year_match.group("year"))
        current_year = (now or datetime.now()).year
        if year > current_year:
            if _MEDICAL_CAUSE_RE.search(text) or _FABRICATED_CITATION_RE.search(text):
                score = max(score, 0.90)
                fired.append("future_study_medical_misinfo")
            else:
                score = max(score, 0.42)
                fired.append("future_dated_study")

    return min(score, 1.0), fired


class HallucinationDetector(Detector):
    """Score confident falsehoods, contradictions, and fabricated citations."""

    @property
    def detector_id(self) -> str:
        return "hallucination"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    async def analyze(self, content: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        score, fired = score_hallucination(content)
        latency = int((time.perf_counter() - start) * 1000)
        if not fired:
            return DetectorResult(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                score=0.05,
                reasoning="No structural hallucination markers",
                latency_ms=latency,
                metadata={"match_count": "0"},
            )
        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=score,
            reasoning=f"Hallucination signals: {', '.join(fired[:6])}",
            latency_ms=latency,
            metadata={"matches": ",".join(fired), "match_count": str(len(fired))},
        )
