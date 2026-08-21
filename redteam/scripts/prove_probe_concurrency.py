#!/usr/bin/env python3
"""Prove probe-level concurrency does not change per-probe decisions/scores.

Runs the same frozen-corpus probe set twice (concurrency=1 vs N) and diffs
probe-by-probe. Does not write campaign headlines and does not change default
campaign behavior.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from aegis_redteam.metrics import FIXTURES_PATH, load_fixtures
from aegis_redteam.mutation.strategies import apply_strategy, list_strategies
from aegis_redteam.probe.bypass import is_bypass
from aegis_redteam.probe.local_stack import (
    HARDENED_STACK,
    STUB_STACK,
    DefenseStackConfig,
    build_defense_stack,
    warmup_stack,
)
from aegis_redteam.settings import settings


@dataclass(frozen=True)
class ProbeKey:
    attack_id: str
    strategy: str
    target: str
    payload_sha16: str


@dataclass
class ProbeOutcome:
    key: ProbeKey
    action: str
    fused_score: float
    bypassed: bool
    latency_ms: int


def _sha16(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


async def _run_one(probe, fixture, strategy: str, sem: asyncio.Semaphore) -> ProbeOutcome:
    payload = apply_strategy(strategy, fixture.payload())
    async with sem:
        t0 = time.perf_counter()
        verdict = await probe.probe(fixture.target, payload)
        latency_ms = int((time.perf_counter() - t0) * 1000)
    action = str(verdict["action"])
    score = float(verdict["fused_score"])
    return ProbeOutcome(
        key=ProbeKey(
            attack_id=fixture.id,
            strategy=strategy,
            target=fixture.target.value,
            payload_sha16=_sha16(payload),
        ),
        action=action,
        fused_score=score,
        bypassed=is_bypass(action, score, settings.detection_threshold),
        latency_ms=latency_ms,
    )


async def run_batch(
    stack: DefenseStackConfig,
    fixtures,
    strategies: list[str],
    *,
    concurrency: int,
) -> list[ProbeOutcome]:
    probe = build_defense_stack(stack)
    sem = asyncio.Semaphore(max(1, concurrency))
    jobs = [
        _run_one(probe, fixture, strategy, sem) for fixture in fixtures for strategy in strategies
    ]
    # Preserve submission order in gather so serial and concurrent produce the
    # same list order for easier debugging; comparison is still key-based.
    return list(await asyncio.gather(*jobs))


def diff_outcomes(
    serial: list[ProbeOutcome],
    concurrent: list[ProbeOutcome],
    *,
    score_eps: float,
) -> dict:
    s_map = {o.key: o for o in serial}
    c_map = {o.key: o for o in concurrent}
    only_s = sorted(set(s_map) - set(c_map), key=lambda k: (k.attack_id, k.strategy))
    only_c = sorted(set(c_map) - set(s_map), key=lambda k: (k.attack_id, k.strategy))
    mismatches: list[dict] = []
    for key in sorted(set(s_map) & set(c_map), key=lambda k: (k.attack_id, k.strategy)):
        a, b = s_map[key], c_map[key]
        score_delta = abs(a.fused_score - b.fused_score)
        if a.action != b.action or a.bypassed != b.bypassed or score_delta > score_eps:
            mismatches.append(
                {
                    "attack_id": key.attack_id,
                    "strategy": key.strategy,
                    "target": key.target,
                    "serial": {
                        "action": a.action,
                        "bypassed": a.bypassed,
                        "fused_score": a.fused_score,
                    },
                    "concurrent": {
                        "action": b.action,
                        "bypassed": b.bypassed,
                        "fused_score": b.fused_score,
                    },
                    "score_delta": score_delta,
                }
            )
    return {
        "serial_count": len(serial),
        "concurrent_count": len(concurrent),
        "only_serial": [asdict(k) for k in only_s],
        "only_concurrent": [asdict(k) for k in only_c],
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "identical": not only_s and not only_c and not mismatches,
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit-attacks", type=int, default=10, help="Frozen-corpus attack subset size")
    p.add_argument(
        "--attack-ids",
        nargs="*",
        default=None,
        help="Explicit attack IDs (overrides --limit-attacks ordering)",
    )
    p.add_argument(
        "--targets",
        nargs="*",
        choices=("input_defense", "output_defense"),
        default=None,
        help="Optional target filter before limit",
    )
    p.add_argument("--concurrency", type=int, default=8, help="Concurrent probe limit to compare")
    p.add_argument("--score-eps", type=float, default=0.0, help="Allowed fused_score abs delta")
    p.add_argument(
        "--profile",
        choices=("stub", "hardened", "both"),
        default="hardened",
        help="Which defense stack(s) to compare",
    )
    p.add_argument("--out", type=Path, default=Path("/tmp/probe_concurrency_diff.json"))
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    attacks = [f for f in load_fixtures(FIXTURES_PATH) if f.is_attack]
    if args.targets:
        allowed = set(args.targets)
        attacks = [f for f in attacks if f.target.value in allowed]
    if args.attack_ids:
        wanted = set(args.attack_ids)
        attacks = [f for f in attacks if f.id in wanted]
        missing = wanted - {f.id for f in attacks}
        if missing:
            raise SystemExit(f"Unknown attack ids: {sorted(missing)}")
    else:
        attacks = attacks[: args.limit_attacks]
    strategies = [sid for sid, _ in list_strategies()]
    profiles: list[tuple[str, DefenseStackConfig]] = []
    if args.profile in ("stub", "both"):
        profiles.append(("stub", STUB_STACK))
    if args.profile in ("hardened", "both"):
        profiles.append(("hardened", HARDENED_STACK))

    report: dict = {
        "corpus": str(FIXTURES_PATH),
        "limit_attacks": args.limit_attacks,
        "attack_ids": [f.id for f in attacks],
        "strategies": strategies,
        "concurrency_compared": args.concurrency,
        "score_eps": args.score_eps,
        "profiles": {},
    }

    overall_ok = True
    for name, stack in profiles:
        print(f"== profile {name}: warmup + serial concurrency=1 ==", flush=True)
        if stack.profile == "hardened":
            warmup_stack(stack)
        t0 = time.perf_counter()
        serial = await run_batch(stack, attacks, strategies, concurrency=1)
        serial_s = time.perf_counter() - t0
        print(
            f"serial done: {len(serial)} probes in {serial_s:.1f}s "
            f"({serial_s / max(len(serial), 1):.2f}s/probe)",
            flush=True,
        )

        print(f"== profile {name}: concurrent concurrency={args.concurrency} ==", flush=True)
        t1 = time.perf_counter()
        concurrent = await run_batch(stack, attacks, strategies, concurrency=args.concurrency)
        conc_s = time.perf_counter() - t1
        print(
            f"concurrent done: {len(concurrent)} probes in {conc_s:.1f}s "
            f"({conc_s / max(len(concurrent), 1):.2f}s/probe wall)",
            flush=True,
        )

        diff = diff_outcomes(serial, concurrent, score_eps=args.score_eps)
        diff["serial_elapsed_s"] = serial_s
        diff["concurrent_elapsed_s"] = conc_s
        diff["speedup"] = (serial_s / conc_s) if conc_s else None
        report["profiles"][name] = diff
        overall_ok = overall_ok and bool(diff["identical"])
        print(
            f"diff identical={diff['identical']} mismatches={diff['mismatch_count']} "
            f"only_serial={len(diff['only_serial'])} "
            f"only_concurrent={len(diff['only_concurrent'])}",
            flush=True,
        )

    args.out.write_text(json.dumps(report, indent=2))
    print(f"wrote {args.out}", flush=True)
    print("OVERALL_IDENTICAL" if overall_ok else "OVERALL_DIFFERS", flush=True)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
