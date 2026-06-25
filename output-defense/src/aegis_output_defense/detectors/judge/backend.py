"""LLM judge backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from aegis_output_defense.models import JudgeVote


@dataclass
class JudgeEnsembleResult:
    votes: list[JudgeVote]
    unsafe_fraction: float
    boosted_score: float
    reasoning: str


class JudgeBackend(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @abstractmethod
    async def evaluate(self, content: str, *, fused_score: float) -> JudgeEnsembleResult: ...
