#!/usr/bin/env python3
"""Dump reserved-corpus adaptive bypass transcripts for M4 class analysis.

Runs hardened-only adaptive campaign with probe concurrency, writes JSONL of
every adaptive-phase bypass (payload, scores, mutation metadata).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from aegis_redteam.metrics import RESERVED_FIXTURES_PATH, load_fixtures
from aegis_redteam.models import RunAdaptiveCampaignRequest
from aegis_redteam.mutation.strategies import list_strategies
from aegis_redteam.probe.local_stack import HARDENED_STACK, build_defense_stack, warmup_stack
from aegis_redteam.service import RedTeamService
from aegis_redteam.settings import settings


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--concurrency", type=int, default=32)
    p.add_argument("--out", type=Path, default=Path("/tmp/reserved_adapt_bypasses.jsonl"))
    p.add_argument("--summary-out", type=Path, default=Path("/tmp/reserved_adapt_summary.json"))
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    attacks = [f for f in load_fixtures(RESERVED_FIXTURES_PATH) if f.is_attack]
    print(
        f"reserved dump: {len(attacks)} attacks × {len(list_strategies())} strategies; "
        f"concurrency={args.concurrency}",
        flush=True,
    )
    warmup_stack(HARDENED_STACK)
    probe = build_defense_stack(HARDENED_STACK)
    service = RedTeamService(probe, threshold=settings.detection_threshold, store_bypasses=False)
    req = RunAdaptiveCampaignRequest(
        rounds=args.rounds,
        store_bypasses=False,
        use_router_mutations=False,
        fixtures_path=str(RESERVED_FIXTURES_PATH),
        probe_concurrency=args.concurrency,
    )
    t0 = time.perf_counter()
    result = await service.run_adaptive_campaign(req)
    elapsed = time.perf_counter() - t0
    report = result.report

    adaptive_bypass = [
        r for r in report.results if r.metadata.get("phase") == "adaptive" and r.bypassed
    ]
    with args.out.open("w", encoding="utf-8") as fh:
        for r in adaptive_bypass:
            fh.write(
                json.dumps(
                    {
                        "attack_id": r.attack_id,
                        "category": r.category,
                        "target": r.target.value,
                        "strategy": r.strategy,
                        "payload": r.payload,
                        "action": r.defense_action,
                        "fused_score": r.fused_score,
                        "detector_scores": r.detector_scores,
                        "round": r.metadata.get("round"),
                        "mutation_kind": r.metadata.get("mutation_kind"),
                        "source_attack_id": r.metadata.get("source_attack_id"),
                        "source_strategy": r.metadata.get("source_strategy"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    from collections import Counter

    summary = {
        "elapsed_s": elapsed,
        "r1_br": report.baseline_bypass_rate,
        "adapt_br": report.adaptive_bypass_rate,
        "adaptive_bypass_count": len(adaptive_bypass),
        "by_attack_id": Counter(r.attack_id for r in adaptive_bypass),
        "by_category": Counter(r.category for r in adaptive_bypass),
        "by_target": Counter(r.target.value for r in adaptive_bypass),
        "by_mutation_kind": Counter(r.metadata.get("mutation_kind", "") for r in adaptive_bypass),
        "by_strategy": Counter(r.strategy for r in adaptive_bypass),
        "by_round": Counter(r.metadata.get("round", "") for r in adaptive_bypass),
    }
    # JSON-serialize Counters
    summary = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in summary.items()}
    args.summary_out.write_text(json.dumps(summary, indent=2))
    print(
        f"wrote {len(adaptive_bypass)} adaptive bypasses → {args.out}\n"
        f"summary → {args.summary_out}\n"
        f"R1 BR={report.baseline_bypass_rate:.1%} Adapt BR={report.adaptive_bypass_rate:.1%} "
        f"elapsed={elapsed:.1f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
