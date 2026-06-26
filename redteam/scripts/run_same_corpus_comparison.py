#!/usr/bin/env python3
"""
Same-corpus before/after comparison: Phase 1 stub vs Phase 2 hardened defenses.

Runs the IDENTICAL attack corpus, strategies, and adaptive rounds against both
backend profiles in-process. Round-1 probe counts are guaranteed equal; adaptive
round probe counts may differ because defense outcomes diverge (expected).

Requires: pip install -e ../input-defense/.[ml] -e ../output-defense/.[ml] -e .
Model-router + XAI_API_KEY needed for LLM adaptive mutations (Grok).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass

from aegis_redteam.clients.model_router import ModelRouterClient
from aegis_redteam.metrics import (
    format_metrics_table,
    format_round_table,
    load_fixtures,
)
from aegis_redteam.models import AdaptiveCampaignReport, RunAdaptiveCampaignRequest
from aegis_redteam.mutation.strategies import list_strategies
from aegis_redteam.probe.local_stack import (
    HARDENED_STACK,
    STUB_STACK,
    DefenseStackConfig,
    build_defense_stack,
    warmup_stack,
)
from aegis_redteam.service import RedTeamService
from aegis_redteam.settings import settings


@dataclass
class CampaignSnapshot:
    profile: str
    report: AdaptiveCampaignReport
    elapsed_s: float


def _configure_streaming_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(line_buffering=True)
            except (ValueError, OSError):
                pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=settings.adaptive_rounds)
    parser.add_argument(
        "--strategies",
        nargs="*",
        default=None,
        help="Baseline strategies (default: all 8)",
    )
    parser.add_argument("--warmup", action="store_true", help="Pre-load ML models")
    parser.add_argument(
        "--no-router-mutations",
        action="store_true",
        help="Disable Grok/router adaptive rephrase (lexical only)",
    )
    parser.add_argument("--stub-only", action="store_true", help="Run stub profile only")
    parser.add_argument("--hardened-only", action="store_true", help="Run hardened only")
    return parser.parse_args()


def _round1_probe_count(report: AdaptiveCampaignReport) -> int:
    if not report.rounds:
        return 0
    return report.rounds[0].total_probes


def _format_same_corpus_table(stub: CampaignSnapshot, hardened: CampaignSnapshot) -> str:
    def _row(label: str, report: AdaptiveCampaignReport) -> list[str]:
        baseline = [r for r in report.results if r.metadata.get("phase") == "baseline"]
        adaptive = [r for r in report.results if r.metadata.get("phase") == "adaptive"]
        b_bypass = sum(1 for r in baseline if r.bypassed)
        a_bypass = sum(1 for r in adaptive if r.bypassed)
        return [
            label,
            str(len(baseline)),
            str(b_bypass),
            f"{report.baseline_bypass_rate:.1%}",
            str(len(adaptive)),
            str(a_bypass),
            f"{report.adaptive_bypass_rate:.1%}",
            f"{report.bypass_rate:.1%}",
        ]

    headers = [
        "Profile",
        "R1 probes",
        "R1 bypass",
        "R1 BR",
        "Adapt probes",
        "Adapt bypass",
        "Adapt BR",
        "Overall BR",
    ]
    rows = [_row("Phase 1 stub", stub.report), _row("Phase 2 hardened", hardened.report)]
    widths = [max(len(headers[i]), max(len(r[i]) for r in rows)) for i in range(len(headers))]

    def fmt(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    sep = "|-" + "-|-".join("-" * w for w in widths) + "-|"
    return "\n".join([fmt(headers), sep] + [fmt(r) for r in rows])


async def _run_profile(
    stack_config: DefenseStackConfig,
    req: RunAdaptiveCampaignRequest,
    router_client: ModelRouterClient | None,
) -> CampaignSnapshot:
    probe = build_defense_stack(stack_config)
    service = RedTeamService(
        probe,
        threshold=settings.detection_threshold,
        store_bypasses=False,
        router_client=router_client,
    )
    started = time.perf_counter()
    result = await service.run_adaptive_campaign(req)
    elapsed = time.perf_counter() - started
    return CampaignSnapshot(
        profile=stack_config.profile,
        report=result.report,
        elapsed_s=elapsed,
    )


async def main() -> int:
    _configure_streaming_output()
    args = _parse_args()

    attacks = [f for f in load_fixtures() if f.is_attack]
    strategy_count = len(args.strategies) if args.strategies else len(list_strategies())
    expected_r1 = len(attacks) * strategy_count

    router_client = None
    use_router = settings.use_router_mutations and not args.no_router_mutations
    if use_router:
        router_client = ModelRouterClient(
            settings.model_router_url,
            model=settings.router_model,
            provider=settings.router_provider,
            timeout=settings.router_timeout,
            max_retries=settings.router_max_retries,
        )

    req = RunAdaptiveCampaignRequest(
        rounds=args.rounds,
        strategies=args.strategies,
        store_bypasses=False,
        use_router_mutations=use_router,
        max_router_blocked=settings.max_router_blocked,
        max_router_bypass=settings.max_router_bypass,
    )

    print(
        f"Same-corpus adaptive campaign: {len(attacks)} attacks × {strategy_count} strategies "
        f"= {expected_r1} round-1 probes per profile",
        file=sys.stderr,
        flush=True,
    )
    if use_router:
        print(
            f"LLM adaptive mutations: ON ({settings.router_provider}/{settings.router_model})",
            file=sys.stderr,
            flush=True,
        )
    else:
        print("LLM adaptive mutations: OFF", file=sys.stderr, flush=True)

    snapshots: list[CampaignSnapshot] = []

    if not args.hardened_only:
        if args.warmup:
            warmup_stack(STUB_STACK)
        print("Running Phase 1 stub profile...", file=sys.stderr, flush=True)
        snapshots.append(await _run_profile(STUB_STACK, req, router_client))

    if not args.stub_only:
        if args.warmup:
            warmup_stack(HARDENED_STACK)
        print("Running Phase 2 hardened profile...", file=sys.stderr, flush=True)
        snapshots.append(await _run_profile(HARDENED_STACK, req, router_client))

    print("AEGIS Red Team — Same-Corpus Before/After Comparison")
    print(f"Corpus: {len(attacks)} attacks | Round-1 strategies: {strategy_count}")
    print(f"Adaptive rounds: {args.rounds} | Threshold: {settings.detection_threshold:.2f}")
    print()

    if len(snapshots) == 2:
        stub, hardened = snapshots[0], snapshots[1]
        assert _round1_probe_count(stub.report) == _round1_probe_count(hardened.report), (
            "Round-1 probe count mismatch — not apples-to-apples"
        )
        assert _round1_probe_count(stub.report) == expected_r1, (
            f"Expected {expected_r1} round-1 probes, got {_round1_probe_count(stub.report)}"
        )
        print("-- Headline comparison (identical round-1 corpus) --")
        print(_format_same_corpus_table(stub, hardened))
        print()
        print(f"Stub elapsed: {stub.elapsed_s:.1f}s | Hardened elapsed: {hardened.elapsed_s:.1f}s")
        print()
        for snap in snapshots:
            print(f"-- {snap.profile} per-round --")
            print(format_round_table(snap.report.rounds))
            print()
    else:
        snap = snapshots[0]
        print(f"-- {snap.profile} only --")
        print(format_round_table(snap.report.rounds))
        print(
            f"Overall BR: {snap.report.bypass_rate:.1%} "
            f"({snap.report.bypass_count}/{snap.report.total_probes})"
        )

    print(
        "Note: Adaptive-round probe counts differ between profiles when defenses "
        "block/allow different payloads — that divergence is the measured effect."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
