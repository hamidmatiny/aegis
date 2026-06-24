"""Detector registry and factory."""

from __future__ import annotations

from aegis_output_defense.detectors.backtranslation import BacktranslationDetector
from aegis_output_defense.detectors.base import Detector
from aegis_output_defense.detectors.judge.detector import JudgeDetector
from aegis_output_defense.detectors.pii import PIIDetector
from aegis_output_defense.detectors.toxicity.detector import ToxicityDetector

ALL_DETECTOR_IDS = ("toxicity", "pii", "backtranslation", "judge")
SCORING_DETECTOR_IDS = ("toxicity", "pii", "backtranslation")
ALWAYS_RUN_IDS = ("toxicity", "pii", "backtranslation")


def build_detector_registry() -> dict[str, Detector]:
    return {
        "toxicity": ToxicityDetector(),
        "pii": PIIDetector(),
        "backtranslation": BacktranslationDetector(),
        "judge": JudgeDetector(),
    }
