"""Classifier detector package."""

from aegis_input_defense.detectors.classifier.backend import ClassifierBackend, ClassifierPrediction
from aegis_input_defense.detectors.classifier.detector import ClassifierDetector
from aegis_input_defense.detectors.classifier.stub_backend import StubClassifierBackend

__all__ = [
    "ClassifierBackend",
    "ClassifierPrediction",
    "ClassifierDetector",
    "StubClassifierBackend",
]
