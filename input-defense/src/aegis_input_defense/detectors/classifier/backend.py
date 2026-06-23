"""Swappable classifier backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ClassifierPrediction:
    """Raw prediction from a classifier backend."""

    label: str
    probability: float
    reasoning: str
    model_id: str


class ClassifierBackend(ABC):
    """
    Pluggable ML classifier backend.

    Swap implementations (stub, HuggingFace Llama-Prompt-Guard-2, fine-tuned DistilBERT)
    without changing fusion logic or the ClassifierDetector wrapper.
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Identifier of the underlying model (for audit metadata)."""

    @abstractmethod
    async def predict(self, text: str) -> ClassifierPrediction:
        """Return injection/jailbreak probability for the given text."""
