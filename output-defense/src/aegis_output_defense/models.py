"""Shared data models for output defense."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class VerdictAction(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    TRANSFORM = "TRANSFORM"
    ESCALATE = "ESCALATE"


class TraceContext(BaseModel):
    trace_id: str | None = None
    request_id: str | None = None


class DetectorResult(BaseModel):
    """Result from a single detector invocation."""

    detector_id: str
    detector_version: str
    score: float = Field(ge=0.0, le=1.0, description="0=safe, 1=harmful/leaked")
    reasoning: str
    latency_ms: int = Field(ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)
    redacted_text: str | None = None


class DetectorScore(BaseModel):
    """Auditable detector score included in OutputVerdict."""

    detector_id: str
    detector_version: str
    score: float
    reasoning: str
    latency_ms: int
    metadata: dict[str, str] = Field(default_factory=dict)


class JudgeVote(BaseModel):
    judge_id: str
    prompt_framing: str
    vote: VerdictAction
    reasoning: str
    latency_ms: int = 0


class OutputVerdict(BaseModel):
    """Fused output defense verdict with full per-detector breakdown."""

    action: VerdictAction
    fused_score: float = Field(ge=0.0, le=1.0)
    detector_scores: list[DetectorScore]
    redacted_content: str | None = None
    escalation_reason: str | None = None
    judge_votes: list[JudgeVote] = Field(default_factory=list)
    total_latency_ms: int = 0
    request_id: str | None = None


class AnalyzeRequest(BaseModel):
    content: str
    tenant_id: str = "default"
    trace: TraceContext | None = None
    original_prompt: str | None = None
    enabled_detectors: list[str] | None = None
    policy_pack_id: str | None = None
    policy_pack_version: str | None = None


class AnalyzeResponse(BaseModel):
    verdict: OutputVerdict


class DetectorInfo(BaseModel):
    detector_id: str
    detector_version: str
    description: str
    is_redactor: bool = False
    conditional: bool = False


class FixtureCase(BaseModel):
    id: str
    label: str
    category: str
    description: str
    content: str

    @property
    def is_attack(self) -> bool:
        return self.label == "attack"

    @property
    def is_benign(self) -> bool:
        return self.label == "benign"


class FixtureScoreRow(BaseModel):
    """Single-pass scores for one fixture (avoids redundant detector/router calls)."""

    case: FixtureCase
    scores: dict[str, float]
    metadata: dict[str, dict[str, str]] = Field(default_factory=dict)


class MetricsReport(BaseModel):
    detector_id: str
    attack_total: int
    attack_caught: int
    attack_success_rate: float
    benign_total: int
    false_positives: int
    false_positive_rate: float
    threshold: float

    def to_row(self) -> dict[str, Any]:
        return {
            "detector": self.detector_id,
            "attacks": self.attack_total,
            "caught": self.attack_caught,
            "ASR": f"{self.attack_success_rate:.1%}",
            "benign": self.benign_total,
            "false_pos": self.false_positives,
            "FPR": f"{self.false_positive_rate:.1%}",
            "threshold": self.threshold,
        }


class AblationMetricsReport(BaseModel):
    omitted_detector: str
    attack_success_rate: float
    false_positive_rate: float
    delta_asr: float
    delta_fpr: float
    threshold: float


class CategoryMetricsReport(BaseModel):
    category: str
    detector_id: str
    attack_total: int
    attack_caught: int
    attack_success_rate: float
    threshold: float
