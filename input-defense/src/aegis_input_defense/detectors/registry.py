"""Detector registry and factory."""

from __future__ import annotations

from aegis_input_defense.detectors.base import Detector
from aegis_input_defense.detectors.classifier import (
    ClassifierBackend,
    ClassifierDetector,
    StubClassifierBackend,
)
from aegis_input_defense.detectors.heuristic import HeuristicDetector
from aegis_input_defense.detectors.known_answer import KnownAnswerDetector
from aegis_input_defense.detectors.perplexity import PerplexityDetector
from aegis_input_defense.detectors.spotlighting import SpotlightingDetector

ALL_DETECTOR_IDS = ("heuristic", "perplexity", "known_answer", "classifier", "spotlighting")
SCORING_DETECTOR_IDS = ("heuristic", "perplexity", "known_answer", "classifier")


def build_detector_registry(
    classifier_backend: ClassifierBackend | None = None,
) -> dict[str, Detector]:
    """Create a registry of all available detectors."""
    return {
        "heuristic": HeuristicDetector(),
        "perplexity": PerplexityDetector(),
        "known_answer": KnownAnswerDetector(),
        "classifier": ClassifierDetector(backend=classifier_backend or StubClassifierBackend()),
        "spotlighting": SpotlightingDetector(),
    }
