"""Shared data models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DefenseTarget(StrEnum):
    INPUT_DEFENSE = "input_defense"
    OUTPUT_DEFENSE = "output_defense"


class AttackFixture(BaseModel):
    id: str
    label: str
    category: str
    description: str
    target: DefenseTarget
    text: str = ""
    content: str = ""

    @property
    def is_attack(self) -> bool:
        return self.label == "attack"

    def payload(self) -> str:
        return self.content if self.target == DefenseTarget.OUTPUT_DEFENSE else self.text


class ProbeResult(BaseModel):
    attack_id: str
    category: str
    target: DefenseTarget
    strategy: str
    payload: str
    defense_action: str
    fused_score: float
    bypassed: bool
    latency_ms: int
    metadata: dict[str, str] = Field(default_factory=dict)


class CampaignSummary(BaseModel):
    campaign_id: str
    started_at: datetime
    completed_at: datetime
    total_probes: int
    bypass_count: int
    bypass_rate: float
    by_target: dict[str, TargetMetrics]


class CampaignReport(BaseModel):
    campaign_id: str
    started_at: datetime
    completed_at: datetime
    results: list[ProbeResult]
    threshold: float
    total_probes: int
    bypass_count: int
    bypass_rate: float
    by_target: dict[str, TargetMetrics]
    by_category: list[CategoryBypassMetrics]


class TargetMetrics(BaseModel):
    target: str
    probes: int
    bypasses: int
    bypass_rate: float


class CategoryBypassMetrics(BaseModel):
    category: str
    target: str
    probes: int
    bypasses: int
    bypass_rate: float


class BypassPattern(BaseModel):
    pattern_hash: str
    attack_id: str
    category: str
    target: DefenseTarget
    strategy: str
    payload: str
    defense_action: str
    fused_score: float
    stored_at: datetime
    source: str = "redteam-campaign"


class RunCampaignRequest(BaseModel):
    targets: list[DefenseTarget] | None = None
    strategies: list[str] | None = None
    categories: list[str] | None = None
    store_bypasses: bool | None = None


class RunAdaptiveCampaignRequest(RunCampaignRequest):
    """Multi-round campaign: baseline fixtures then adaptive mutations."""

    rounds: int = Field(default=3, ge=1, le=5)
    max_variants_per_bypass: int = Field(default=4, ge=0, le=20)
    use_router_mutations: bool = True
    max_router_blocked: int = Field(default=15, ge=0, le=100)
    max_router_bypass: int = Field(default=5, ge=0, le=50)


class RoundReport(BaseModel):
    round_number: int
    total_probes: int
    bypass_count: int
    bypass_rate: float
    variants_generated: int = 0


class AdaptiveCampaignReport(CampaignReport):
    rounds: list[RoundReport] = Field(default_factory=list)
    baseline_bypass_rate: float = 0.0
    adaptive_bypass_rate: float = 0.0


class RunCampaignResponse(BaseModel):
    report: CampaignReport
    patterns_stored: int


class RunAdaptiveCampaignResponse(BaseModel):
    report: AdaptiveCampaignReport
    patterns_stored: int


class ProbeRequest(BaseModel):
    target: DefenseTarget
    payload: str
    strategy: str = "identity"
    attack_id: str = "manual-probe"


class ProbeResponse(BaseModel):
    result: ProbeResult


class StrategyInfo(BaseModel):
    strategy_id: str
    description: str


class MetricsReport(BaseModel):
    target: str
    strategy: str
    attack_total: int
    bypass_count: int
    bypass_rate: float
    threshold: float

    def to_row(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "strategy": self.strategy,
            "attacks": self.attack_total,
            "bypasses": self.bypass_count,
            "BR": f"{self.bypass_rate:.1%}",
            "threshold": self.threshold,
        }
