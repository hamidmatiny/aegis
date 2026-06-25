"""Detector registry and factory."""

from __future__ import annotations

from aegis_input_defense.detectors.base import Detector
from aegis_input_defense.detectors.classifier import (
    ClassifierBackend,
    ClassifierDetector,
    PromptGuardBackend,
    StubClassifierBackend,
)
from aegis_input_defense.detectors.heuristic import HeuristicDetector
from aegis_input_defense.detectors.known_answer import KnownAnswerDetector
from aegis_input_defense.detectors.perplexity import PerplexityDetector
from aegis_input_defense.detectors.spotlighting import SpotlightingDetector
from aegis_input_defense.settings import settings

ALL_DETECTOR_IDS = ("heuristic", "perplexity", "known_answer", "classifier", "spotlighting")
SCORING_DETECTOR_IDS = ("heuristic", "perplexity", "known_answer", "classifier")


def build_classifier_backend(
    backend: str | None = None,
    *,
    model_id: str | None = None,
) -> ClassifierBackend:
    """Create classifier backend from settings or explicit override."""
    selected = backend or settings.classifier_backend
    if selected == "stub":
        return StubClassifierBackend()
    return PromptGuardBackend(model_id=model_id or settings.prompt_guard_model_id)


def build_detector_registry(
    classifier_backend: ClassifierBackend | None = None,
    *,
    perplexity_backend: str | None = None,
) -> dict[str, Detector]:
    """Create a registry of all available detectors."""
    ppl_backend = perplexity_backend or settings.perplexity_backend
    return {
        "heuristic": HeuristicDetector(),
        "perplexity": PerplexityDetector(
            backend=ppl_backend,
            lm_model_id=settings.perplexity_model_id,
        ),
        "known_answer": KnownAnswerDetector(),
        "classifier": ClassifierDetector(
            backend=classifier_backend or build_classifier_backend(),
        ),
        "spotlighting": SpotlightingDetector(),
    }
