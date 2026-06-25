"""Backtranslation consistency backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BacktranslationResult:
    score: float
    reasoning: str
    model_id: str
    metadata: dict[str, str]


class BacktranslationBackend(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @abstractmethod
    async def evaluate(
        self,
        content: str,
        *,
        original_prompt: str | None = None,
    ) -> BacktranslationResult: ...
