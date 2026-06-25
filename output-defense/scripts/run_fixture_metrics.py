#!/usr/bin/env python3
"""Run fixture metrics with explicit backend selection and execution audit."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import httpx

from aegis_output_defense.backend_audit import audit_backend_execution
from aegis_output_defense.detectors.registry import build_detector_registry
from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.metrics import (
    compute_category_metrics,
    compute_metrics,
    format_category_metrics_table,
    format_metrics_table,
    load_fixtures,
)
from aegis_output_defense.ml.loader import warmup_models
from aegis_output_defense.provenance import format_backend_audit
from aegis_output_defense.service import OutputDefenseService
from aegis_output_defense.settings import settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--toxicity-backend",
        choices=("stub", "toxic-bert"),
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_TOXICITY_BACKEND", "toxic-bert"),
    )
    parser.add_argument(
        "--pii-backend",
        choices=("regex", "ner"),
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_PII_BACKEND", "ner"),
    )
    parser.add_argument(
        "--backtranslation-backend",
        choices=("stub", "router"),
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_BACKEND", "stub"),
    )
    parser.add_argument(
        "--judge-backend",
        choices=("stub", "router"),
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_JUDGE_BACKEND", "stub"),
    )
    parser.add_argument("--warmup", action="store_true", help="Pre-load ML models before scoring")
    parser.add_argument(
        "--check-router",
        action="store_true",
        default=True,
        help="Probe AEGIS_MODEL_ROUTER_URL /health before run (default: on)",
    )
    parser.add_argument(
        "--no-check-router",
        action="store_false",
        dest="check_router",
        help="Skip model-router health probe",
    )
    return parser.parse_args()


async def _probe_router(url: str) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url.rstrip('/')}/health")
            resp.raise_for_status()
            return True, resp.text.strip()[:120]
    except Exception as exc:
        return False, str(exc)


async def main() -> int:
    args = _parse_args()
    router_url = settings.model_router_url
    router_ok = False
    router_detail = "not probed"
    if args.check_router:
        router_ok, router_detail = await _probe_router(router_url)

    if args.warmup:
        warmup_models(
            toxicity=args.toxicity_backend == "toxic-bert",
            pii_ner=args.pii_backend == "ner",
        )

    fixtures = load_fixtures()
    requested = {
        "toxicity": args.toxicity_backend,
        "pii": args.pii_backend,
        "backtranslation": args.backtranslation_backend,
        "judge": args.judge_backend,
    }
    registry = build_detector_registry(
        toxicity_backend=args.toxicity_backend,
        pii_backend=args.pii_backend,
        backtranslation_backend=args.backtranslation_backend,
        judge_backend=args.judge_backend,
    )
    service = OutputDefenseService(detectors=registry)
    threshold = detection_threshold()

    start = time.perf_counter()
    reports = await compute_metrics(service, fixtures, threshold=threshold)
    category_reports = await compute_category_metrics(service, fixtures, threshold=threshold)
    audit = await audit_backend_execution(
        service, fixtures, requested=requested, threshold=threshold
    )
    elapsed = time.perf_counter() - start

    attacks = sum(1 for f in fixtures if f.is_attack)
    benign = sum(1 for f in fixtures if f.is_benign)

    print("AEGIS Output Defense — Fixture Metrics Report")
    print(
        f"Requested backends: toxicity={args.toxicity_backend}, pii={args.pii_backend}, "
        f"backtranslation={args.backtranslation_backend}, judge={args.judge_backend}"
    )
    print(f"model-router: url={router_url} reachable={router_ok} detail={router_detail!r}")
    if args.backtranslation_backend == "router" and not router_ok:
        print(
            "WARNING: backtranslation-backend=router but model-router unreachable — "
            "expect stub-fallback-router-error execution paths"
        )
    print(f"Fixtures: {len(fixtures)} total ({attacks} attacks, {benign} benign)")
    print(f"Detection threshold: {threshold:.2f}")
    print(f"Scoring time: {elapsed:.1f}s")
    print()
    print(format_backend_audit(audit))
    print()
    print("-- Aggregate --")
    print(format_metrics_table(reports))
    print()
    print("-- ASR by Attack Category --")
    print(format_category_metrics_table(category_reports))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
