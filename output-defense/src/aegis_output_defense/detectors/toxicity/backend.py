"""Toxicity classifier backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToxicityPrediction:
    label: str
    probability: float
    reasoning: str
    model_id: str


class ToxicityBackend(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @abstractmethod
    async def predict(self, content: str) -> ToxicityPrediction: ...
