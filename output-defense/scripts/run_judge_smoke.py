#!/usr/bin/env python3
"""Run LLM judge ensemble on ambiguous-band fixture items via model-router."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from aegis_output_defense.detectors.judge.detector import JudgeDetector
from aegis_output_defense.detectors.registry import build_detector_registry
from aegis_output_defense.fusion import detection_threshold, is_ambiguous_score
from aegis_output_defense.metrics import load_fixtures
from aegis_output_defense.service import OutputDefenseService
from aegis_output_defense.settings import settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="Max ambiguous cases to judge")
    parser.add_argument(
        "--judge-provider",
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_JUDGE_PROVIDER", settings.judge_provider),
    )
    parser.add_argument(
        "--judge-model",
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_JUDGE_MODEL", settings.judge_model),
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    fixtures = load_fixtures()
    scoring = OutputDefenseService(
        detectors=build_detector_registry(
            toxicity_backend="stub",
            pii_backend="regex",
            backtranslation_backend="stub",
            judge_backend="stub",
        )
    )
    judge_service = OutputDefenseService(
        detectors=build_detector_registry(
            toxicity_backend="stub",
            pii_backend="regex",
            backtranslation_backend="stub",
            judge_backend="router",
        )
    )

    threshold = detection_threshold()
    ambiguous: list[tuple] = []
    for case in fixtures:
        if not case.is_attack:
            continue
        verdict = await scoring.analyze_all(case.content.strip(), invoke_judge=False)
        if is_ambiguous_score(verdict.fused_score):
            ambiguous.append((case, verdict.fused_score))

    ambiguous.sort(key=lambda item: item[1])
    selected = ambiguous[: args.limit]

    print("AEGIS Output Defense — Judge ensemble smoke (ambiguous band)")
    print(
        f"Judge route: provider={args.judge_provider!r} model={args.judge_model!r} "
        f"url={settings.model_router_url}"
    )
    print(f"Ambiguous band: 0.45–0.70 (threshold={threshold:.2f})")
    print(f"Found {len(ambiguous)} attack fixtures in band; judging {len(selected)}")
    print()

    if not selected:
        print("No ambiguous-band attack fixtures found.")
        return 0

    judge_detector = judge_service.detectors["judge"]
    if not isinstance(judge_detector, JudgeDetector):
        print("Judge detector not configured", file=sys.stderr)
        return 1

    for case, pre_fused in selected:
        result, votes = await judge_detector.analyze_with_votes(
            case.content.strip(),
            fused_score=pre_fused,
        )
        unsafe = sum(1 for v in votes if v.vote.value in ("BLOCK", "ESCALATE"))
        majority = "UNSAFE" if unsafe >= 2 else ("SAFE" if unsafe == 0 else "SPLIT")
        print(f"=== {case.id} ({case.category}) pre_fused={pre_fused:.3f} ===")
        print(f"Majority: {majority} ({unsafe}/{len(votes)} unsafe votes)")
        print(f"Boosted score: {result.score:.3f}")
        for vote in votes:
            print(f"  - {vote.judge_id}: {vote.vote.value} — {vote.reasoning}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
