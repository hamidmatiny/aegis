#!/usr/bin/env python3
"""Run H3 evidence suite: same-corpus campaign + ablation on real backends."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REDTEAM = REPO_ROOT / "redteam"
INPUT = REPO_ROOT / "input-defense"
OUTPUT = REPO_ROOT / "output-defense"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--warmup", action="store_true")
    parser.add_argument(
        "--no-router-mutations",
        action="store_true",
        help="Skip Grok adaptive mutations in campaign",
    )
    parser.add_argument("--skip-campaign", action="store_true")
    parser.add_argument("--skip-ablation", action="store_true")
    return parser.parse_args()


def _run(cmd: list[str], *, cwd: Path) -> int:
    print(f"\n>>> {' '.join(cmd)}", file=sys.stderr, flush=True)
    return subprocess.call(cmd, cwd=cwd)


def main() -> int:
    args = _parse_args()
    py = sys.executable

    print("AEGIS H3 Evidence Suite (Phase 2 real backends as primary)")
    print("=" * 60)

    if not args.skip_campaign:
        campaign_cmd = [
            py,
            "scripts/run_same_corpus_comparison.py",
            "--rounds",
            str(args.rounds),
        ]
        if args.warmup:
            campaign_cmd.append("--warmup")
        if args.no_router_mutations:
            campaign_cmd.append("--no-router-mutations")
        code = _run(campaign_cmd, cwd=REDTEAM)
        if code != 0:
            return code

    if not args.skip_ablation:
        input_cmd = [
            py,
            "scripts/run_ablation_study.py",
            "--classifier-backend",
            "prompt-guard",
            "--perplexity-backend",
            "lm",
        ]
        if args.warmup:
            input_cmd.append("--warmup")
        code = _run(input_cmd, cwd=INPUT)
        if code != 0:
            return code

        output_cmd = [
            py,
            "scripts/run_ablation_study.py",
            "--toxicity-backend",
            "toxic-bert",
            "--pii-backend",
            "ner",
            "--backtranslation-backend",
            "router",
        ]
        if args.warmup:
            output_cmd.append("--warmup")
        code = _run(output_cmd, cwd=OUTPUT)
        if code != 0:
            return code

    print("\nDone. See RESULTS.md for interpretation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
