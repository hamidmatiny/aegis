#!/usr/bin/env python3
"""Diagnose adaptive convergence: bypass examples + per-detector scores."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from aegis_redteam.models import DefenseTarget, RunAdaptiveCampaignRequest
from aegis_redteam.probe.bypass import is_bypass
from aegis_redteam.probe.local_stack import (
    HARDENED_STACK,
    STUB_STACK,
    build_defense_stack,
    warmup_stack,
)
from aegis_redteam.service import RedTeamService
from aegis_redteam.settings import settings

OUTPUT = Path(__file__).resolve().parent.parent / "artifacts" / "convergence_analysis.json"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--warmup", action="store_true")
    p.add_argument("--no-router-mutations", action="store_true")
    p.add_argument("--profile", choices=("hardened", "stub", "both"), default="hardened")
    p.add_argument("--out", type=Path, default=OUTPUT)
    p.add_argument("--max-examples", type=int, default=10)
    return p.parse_args()


async def _detector_breakdown(probe_stack, target: DefenseTarget, payload: str) -> dict:
    if target == DefenseTarget.INPUT_DEFENSE:
        verdict = await probe_stack._input.analyze_all(payload)
    else:
        verdict = await probe_stack._output.analyze_all(payload, invoke_judge=False)
    scores = {s.detector_id: round(s.score, 4) for s in verdict.detector_scores}
    return {
        "action": str(verdict.action),
        "fused_score": round(verdict.fused_score, 4),
        "detector_scores": scores,
        "escalation_reason": verdict.escalation_reason,
    }


async def _run_profile(profile: str, req: RunAdaptiveCampaignRequest) -> dict:
    stack_cfg = HARDENED_STACK if profile == "hardened" else STUB_STACK
    probe = build_defense_stack(stack_cfg)
    service = RedTeamService(probe, threshold=settings.detection_threshold, store_bypasses=False)
    result = await service.run_adaptive_campaign(req)
    report = result.report

    r23_bypasses = [
        r for r in report.results if r.bypassed and r.metadata.get("phase") == "adaptive"
    ]
    r3_bypasses = [r for r in r23_bypasses if r.metadata.get("round") == "3"]

    examples = []
    for r in r23_bypasses[:10]:
        detail = await _detector_breakdown(probe, r.target, r.payload)
        examples.append(
            {
                "round": r.metadata.get("round"),
                "attack_id": r.attack_id,
                "target": r.target.value,
                "category": r.category,
                "strategy": r.strategy,
                "mutation_kind": r.metadata.get("mutation_kind", "lexical"),
                "source_attack_id": r.metadata.get("source_attack_id"),
                "source_strategy": r.metadata.get("source_strategy"),
                "defense_action": r.defense_action,
                "fused_score_campaign": r.fused_score,
                "payload_preview": r.payload[:500],
                "payload_len": len(r.payload),
                "rescore": detail,
            }
        )

    r3_detailed = []
    for r in r3_bypasses[:8]:
        detail = await _detector_breakdown(probe, r.target, r.payload)
        max_det = max(detail["detector_scores"].values()) if detail["detector_scores"] else 0.0
        r3_detailed.append(
            {
                "attack_id": r.attack_id,
                "strategy": r.strategy,
                "target": r.target.value,
                "fused": detail["fused_score"],
                "action": detail["action"],
                "max_detector": max_det,
                "detector_scores": detail["detector_scores"],
                "fusion_gap": round(max_det - detail["fused_score"], 4),
                "payload_preview": r.payload[:400],
            }
        )

    strategy_counts = Counter(r.strategy for r in r23_bypasses)
    kind_counts = Counter(r.metadata.get("mutation_kind", "lexical") for r in r23_bypasses)

    return {
        "profile": profile,
        "rounds": [r.model_dump() for r in report.rounds],
        "overall_bypass_rate": report.bypass_rate,
        "baseline_bypass_rate": report.baseline_bypass_rate,
        "adaptive_bypass_rate": report.adaptive_bypass_rate,
        "round23_bypass_count": len(r23_bypasses),
        "round3_bypass_count": len(r3_bypasses),
        "round23_strategy_breakdown": dict(strategy_counts.most_common()),
        "round23_mutation_kind": dict(kind_counts),
        "examples_round23": examples,
        "round3_detector_analysis": r3_detailed,
    }


async def _ceiling_test(hardened_r3_bypasses: list[dict]) -> list[dict]:
    """Score hardened R3 bypass payloads against stub stack — ceiling check."""
    if not hardened_r3_bypasses:
        return []
    stub_probe = build_defense_stack(STUB_STACK)
    out = []
    for item in hardened_r3_bypasses[:8]:
        target = DefenseTarget(item["target"])
        payload = item["payload_preview"]
        # payload_preview may be truncated — skip if we need full; use from examples
        detail = await _detector_breakdown(stub_probe, target, payload)
        out.append(
            {
                "attack_id": item["attack_id"],
                "stub_action": detail["action"],
                "stub_fused": detail["fused_score"],
                "stub_max_detector": max(detail["detector_scores"].values())
                if detail["detector_scores"]
                else 0.0,
                "hardened_fused": item["fused"],
                "also_bypasses_stub": is_bypass(
                    detail["action"], detail["fused_score"], settings.detection_threshold
                ),
            }
        )
    return out


async def main() -> int:
    args = _parse_args()
    if args.warmup:
        warmup_stack(HARDENED_STACK)
        warmup_stack(STUB_STACK)

    req = RunAdaptiveCampaignRequest(
        rounds=args.rounds,
        store_bypasses=False,
        use_router_mutations=not args.no_router_mutations,
    )

    profiles = ["hardened", "stub"] if args.profile == "both" else [args.profile]
    results: dict = {"threshold": settings.detection_threshold, "profiles": {}}

    for profile in profiles:
        print(f"Running {profile} campaign...", file=sys.stderr, flush=True)
        results["profiles"][profile] = await _run_profile(profile, req)

    if args.profile == "both" and "hardened" in results["profiles"]:
        h = results["profiles"]["hardened"]
        results["ceiling_test_truncated"] = await _ceiling_test(
            h.get("round3_detector_analysis", [])
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
