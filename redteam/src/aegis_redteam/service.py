"""Red-team orchestration service."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from aegis_redteam.adaptive.variants import generate_adaptive_variants
from aegis_redteam.clients.model_router import ModelRouterClient
from aegis_redteam.metrics import build_campaign_report, load_fixtures
from aegis_redteam.models import (
    AdaptiveCampaignReport,
    AttackFixture,
    BypassPattern,
    CampaignReport,
    CampaignSummary,
    DefenseTarget,
    ProbeRequest,
    ProbeResponse,
    ProbeResult,
    RoundReport,
    RunAdaptiveCampaignRequest,
    RunAdaptiveCampaignResponse,
    RunCampaignRequest,
    RunCampaignResponse,
    StrategyInfo,
)
from aegis_redteam.mutation.strategies import (
    apply_strategy,
    list_strategies,
    normalize_strategy_ids,
)
from aegis_redteam.probe.bypass import is_bypass
from aegis_redteam.probe.client import DefenseClient
from aegis_redteam.probe.local_stack import LocalDefenseProbe
from aegis_redteam.store.memory import MemoryPatternStore
from aegis_redteam.store.postgres import PostgresPatternStore


class RedTeamService:
    """Runs mutation strategies against defense services and records bypasses."""

    def __init__(
        self,
        defense_client: DefenseClient | LocalDefenseProbe,
        *,
        threshold: float = 0.50,
        database_url: str = "",
        store_bypasses: bool = True,
        router_client: ModelRouterClient | None = None,
    ) -> None:
        self._defense = defense_client
        self._threshold = threshold
        self._router_client = router_client
        self._memory_store = MemoryPatternStore()
        self._postgres = PostgresPatternStore(database_url) if database_url else None
        self._store_bypasses = store_bypasses
        self._campaigns: dict[str, CampaignReport] = {}

    def list_strategies(self) -> list[StrategyInfo]:
        return [StrategyInfo(strategy_id=sid, description=desc) for sid, desc in list_strategies()]

    def list_patterns(self) -> list[BypassPattern]:
        return self._memory_store.list_patterns()

    def get_campaign(self, campaign_id: str) -> CampaignReport:
        if campaign_id not in self._campaigns:
            raise KeyError(f"Campaign {campaign_id!r} not found")
        return self._campaigns[campaign_id]

    def list_campaigns(self) -> list[CampaignSummary]:
        summaries: list[CampaignSummary] = []
        for report in self._campaigns.values():
            summaries.append(
                CampaignSummary(
                    campaign_id=report.campaign_id,
                    started_at=report.started_at,
                    completed_at=report.completed_at,
                    total_probes=report.total_probes,
                    bypass_count=report.bypass_count,
                    bypass_rate=report.bypass_rate,
                    by_target=report.by_target,
                )
            )
        summaries.sort(key=lambda s: s.started_at, reverse=True)
        return summaries

    async def probe(self, req: ProbeRequest) -> ProbeResponse:
        result = await self._run_probe(
            attack_id=req.attack_id,
            category="manual",
            target=req.target,
            strategy=req.strategy,
            payload=req.payload,
        )
        if self._store_bypasses:
            self._persist_bypass(result)
        return ProbeResponse(result=result)

    async def run_campaign(self, req: RunCampaignRequest) -> RunCampaignResponse:
        fixtures = load_fixtures()
        fixtures = [f for f in fixtures if f.is_attack]

        if req.targets:
            allowed = {t.value for t in req.targets}
            fixtures = [f for f in fixtures if f.target.value in allowed]
        if req.categories:
            fixtures = [f for f in fixtures if f.category in req.categories]

        strategies = normalize_strategy_ids(req.strategies)
        store = req.store_bypasses if req.store_bypasses is not None else self._store_bypasses

        started = datetime.now(tz=UTC)
        campaign_id = f"camp-{int(started.timestamp() * 1000)}"
        results: list[ProbeResult] = []

        for fixture in fixtures:
            for strategy in strategies:
                mutated = apply_strategy(strategy, fixture.payload())
                result = await self._run_probe(
                    attack_id=fixture.id,
                    category=fixture.category,
                    target=fixture.target,
                    strategy=strategy,
                    payload=mutated,
                )
                results.append(result)
                if store:
                    self._persist_bypass(result)

        completed = datetime.now(tz=UTC)
        report = build_campaign_report(
            campaign_id,
            results,
            threshold=self._threshold,
            started_at=started,
            completed_at=completed,
        )
        self._campaigns[campaign_id] = report
        patterns_stored = sum(1 for r in results if r.bypassed) if store else 0
        return RunCampaignResponse(report=report, patterns_stored=patterns_stored)

    async def run_adaptive_campaign(
        self, req: RunAdaptiveCampaignRequest
    ) -> RunAdaptiveCampaignResponse:
        fixtures = load_fixtures()
        fixtures = [f for f in fixtures if f.is_attack]

        if req.targets:
            allowed = {t.value for t in req.targets}
            fixtures = [f for f in fixtures if f.target.value in allowed]
        if req.categories:
            fixtures = [f for f in fixtures if f.category in req.categories]

        strategies = normalize_strategy_ids(req.strategies)
        store = req.store_bypasses if req.store_bypasses is not None else self._store_bypasses

        started = datetime.now(tz=UTC)
        campaign_id = f"adaptive-{int(started.timestamp() * 1000)}"
        all_results: list[ProbeResult] = []
        round_reports: list[RoundReport] = []

        for round_num in range(1, req.rounds + 1):
            round_results: list[ProbeResult] = []
            variants_generated = 0

            if round_num == 1:
                for fixture in fixtures:
                    for strategy in strategies:
                        mutated = apply_strategy(strategy, fixture.payload())
                        result = await self._run_probe(
                            attack_id=fixture.id,
                            category=fixture.category,
                            target=fixture.target,
                            strategy=strategy,
                            payload=mutated,
                            metadata={"round": str(round_num), "phase": "baseline"},
                        )
                        round_results.append(result)
            else:
                prev_round = str(round_num - 1)
                prior_round_probes = [
                    r for r in all_results if r.metadata.get("round") == prev_round
                ]
                router = self._router_client if req.use_router_mutations else None
                variants = await generate_adaptive_variants(
                    prior_round_probes,
                    round_number=round_num,
                    max_lexical_per_bypass=req.max_variants_per_bypass,
                    router_client=router,
                    max_router_blocked=req.max_router_blocked,
                    max_router_bypass=req.max_router_bypass,
                )
                variants_generated = len(variants)
                for variant in variants:
                    result = await self._run_probe(
                        attack_id=variant.attack_id,
                        category=variant.category,
                        target=variant.target,
                        strategy=variant.strategy,
                        payload=variant.payload,
                        metadata={
                            "round": str(round_num),
                            "phase": "adaptive",
                            "mutation_kind": variant.mutation_kind,
                            "source_attack_id": variant.source_attack_id,
                            "source_strategy": variant.source_strategy,
                        },
                    )
                    round_results.append(result)

            for result in round_results:
                if store:
                    self._persist_bypass(result)
            all_results.extend(round_results)

            bypass_count = sum(1 for r in round_results if r.bypassed)
            round_reports.append(
                RoundReport(
                    round_number=round_num,
                    total_probes=len(round_results),
                    bypass_count=bypass_count,
                    bypass_rate=bypass_count / len(round_results) if round_results else 0.0,
                    variants_generated=variants_generated,
                )
            )

        completed = datetime.now(tz=UTC)
        base_report = build_campaign_report(
            campaign_id,
            all_results,
            threshold=self._threshold,
            started_at=started,
            completed_at=completed,
        )

        baseline_rows = [r for r in all_results if r.metadata.get("phase") == "baseline"]
        adaptive_rows = [r for r in all_results if r.metadata.get("phase") == "adaptive"]
        baseline_bypass_rate = (
            sum(1 for r in baseline_rows if r.bypassed) / len(baseline_rows)
            if baseline_rows
            else 0.0
        )
        adaptive_bypass_rate = (
            sum(1 for r in adaptive_rows if r.bypassed) / len(adaptive_rows)
            if adaptive_rows
            else 0.0
        )

        report = AdaptiveCampaignReport(
            **base_report.model_dump(),
            rounds=round_reports,
            baseline_bypass_rate=baseline_bypass_rate,
            adaptive_bypass_rate=adaptive_bypass_rate,
        )
        self._campaigns[campaign_id] = report
        patterns_stored = sum(1 for r in all_results if r.bypassed) if store else 0
        return RunAdaptiveCampaignResponse(report=report, patterns_stored=patterns_stored)

    async def _run_probe(
        self,
        *,
        attack_id: str,
        category: str,
        target: DefenseTarget,
        strategy: str,
        payload: str,
        metadata: dict[str, str] | None = None,
    ) -> ProbeResult:
        start = time.perf_counter()
        verdict: dict[str, Any] = await self._defense.probe(target, payload)
        latency = int((time.perf_counter() - start) * 1000)
        action = str(verdict["action"])
        score = float(verdict["fused_score"])
        return ProbeResult(
            attack_id=attack_id,
            category=category,
            target=target,
            strategy=strategy,
            payload=payload,
            defense_action=action,
            fused_score=score,
            bypassed=is_bypass(action, score, self._threshold),
            latency_ms=latency,
            metadata=metadata or {},
        )

    def _persist_bypass(self, result: ProbeResult) -> None:
        pattern = self._memory_store.store_probe(result)
        if pattern and self._postgres:
            self._postgres.save(pattern)

    @staticmethod
    def filter_fixtures(
        fixtures: list[AttackFixture],
        *,
        targets: list[DefenseTarget] | None = None,
        categories: list[str] | None = None,
    ) -> list[AttackFixture]:
        out = [f for f in fixtures if f.is_attack]
        if targets:
            allowed = set(targets)
            out = [f for f in out if f.target in allowed]
        if categories:
            out = [f for f in out if f.category in categories]
        return out
