"""Common detector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aegis_input_defense.models import DetectorResult


@dataclass
class DetectorContext:
    """Optional context passed to detectors."""

    trusted_instruction: str | None = None
    request_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class Detector(ABC):
    """Base class for all input defense detectors."""

    @property
    @abstractmethod
    def detector_id(self) -> str:
        """Stable identifier used in audit logs and config."""

    @property
    @abstractmethod
    def detector_version(self) -> str:
        """Semantic version of this detector implementation."""

    @property
    def is_transform(self) -> bool:
        """Transform detectors rewrite content rather than score risk."""
        return False

    @property
    def description(self) -> str:
        return self.__class__.__doc__ or ""

    @abstractmethod
    async def analyze(self, text: str, context: DetectorContext | None = None) -> DetectorResult:
        """Analyze input text and return a scored result."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.detector_id!r})"
