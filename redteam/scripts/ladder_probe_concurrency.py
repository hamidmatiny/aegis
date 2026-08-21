#!/usr/bin/env python3
"""Pick highest sustainable probe concurrency (8/16/32) without errors/timeouts.

Runs a mixed frozen subset at each level (concurrent only). Does not change
campaign defaults. Exit 0 always; prints CHOICE=<n> for the winner.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
import time
import traceback
from pathlib import Path

from aegis_redteam.metrics import FIXTURES_PATH, load_fixtures
from aegis_redteam.mutation.strategies import list_strategies
from aegis_redteam.probe.local_stack import HARDENED_STACK, warmup_stack

_PROOF = Path(__file__).resolve().parent / "prove_probe_concurrency.py"
_spec = importlib.util.spec_from_file_location("prove_probe_concurrency", _PROOF)
assert _spec and _spec.loader
_prove = importlib.util.module_from_spec(_spec)
sys.modules["prove_probe_concurrency"] = _prove
_spec.loader.exec_module(_prove)
run_batch = _prove.run_batch


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit-attacks", type=int, default=8)
    p.add_argument("--levels", nargs="+", type=int, default=[8, 16, 32])
    p.add_argument("--timeout-s", type=float, default=900.0, help="Per-level wall timeout")
    return p.parse_args()


async def _run_level(attacks, strategies, concurrency: int, timeout_s: float) -> dict:
    t0 = time.perf_counter()
    try:
        outcomes = await asyncio.wait_for(
            run_batch(HARDENED_STACK, attacks, strategies, concurrency=concurrency),
            timeout=timeout_s,
        )
        elapsed = time.perf_counter() - t0
        return {
            "concurrency": concurrency,
            "ok": True,
            "probes": len(outcomes),
            "elapsed_s": elapsed,
            "wall_s_per_probe": elapsed / max(len(outcomes), 1),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 — ladder must record failures
        elapsed = time.perf_counter() - t0
        return {
            "concurrency": concurrency,
            "ok": False,
            "probes": 0,
            "elapsed_s": elapsed,
            "wall_s_per_probe": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


async def main() -> int:
    args = _parse_args()
    all_attacks = [f for f in load_fixtures(FIXTURES_PATH) if f.is_attack]
    # Mixed input/output so ladder stresses router backtranslation, not only PG.
    inputs = [f for f in all_attacks if f.target.value == "input_defense"]
    outputs = [f for f in all_attacks if f.target.value == "output_defense"]
    half = max(1, args.limit_attacks // 2)
    attacks = inputs[:half] + outputs[: args.limit_attacks - half]
    strategies = [sid for sid, _ in list_strategies()]
    n_probes = len(attacks) * len(strategies)
    print(
        f"ladder: {len(attacks)} attacks "
        f"(in={sum(1 for a in attacks if a.target.value=='input_defense')} "
        f"out={sum(1 for a in attacks if a.target.value=='output_defense')}) "
        f"× {len(strategies)} = {n_probes} probes",
        flush=True,
    )
    print("warmup hardened...", flush=True)
    warmup_stack(HARDENED_STACK)

    results: list[dict] = []
    for level in args.levels:
        print(f"\n== concurrency={level} ==", flush=True)
        row = await _run_level(attacks, strategies, level, args.timeout_s)
        results.append(row)
        if row["ok"]:
            print(
                f"OK probes={row['probes']} elapsed={row['elapsed_s']:.1f}s "
                f"wall/probe={row['wall_s_per_probe']:.2f}s",
                flush=True,
            )
        else:
            print(f"FAIL after {row['elapsed_s']:.1f}s: {row['error']}", flush=True)

    # Prefer highest ok level whose wall/probe is not worse than 1.25× the best ok.
    ok_rows = [r for r in results if r["ok"]]
    if not ok_rows:
        print("CHOICE=1", flush=True)
        print("NO_SUSTAINABLE_LEVEL", flush=True)
        return 1
    best_rate = min(r["wall_s_per_probe"] for r in ok_rows)
    sustainable = [r for r in ok_rows if r["wall_s_per_probe"] <= best_rate * 1.25]
    choice = max(r["concurrency"] for r in sustainable)
    print(f"\nCHOICE={choice}", flush=True)
    for r in results:
        print(
            f"  level={r['concurrency']} ok={r['ok']} "
            f"elapsed={r['elapsed_s']:.1f} wall/probe={r['wall_s_per_probe']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
