#!/usr/bin/env python3
"""Run fixture metrics with explicit backend selection and execution audit."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import httpx

from aegis_output_defense.backend_audit import audit_backend_execution_from_rows
from aegis_output_defense.clients.model_router import ModelRouterClient
from aegis_output_defense.detectors.registry import build_detector_registry
from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.metrics import (
    compute_category_metrics_from_rows,
    compute_metrics_from_rows,
    format_category_metrics_table,
    format_metrics_table,
    load_fixtures,
    score_fixtures,
)
from aegis_output_defense.ml.loader import warmup_models
from aegis_output_defense.provenance import format_backend_audit
from aegis_output_defense.service import OutputDefenseService
from aegis_output_defense.settings import settings


def _configure_streaming_output() -> None:
    """Ensure progress lines appear immediately (especially when stdout is piped)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(line_buffering=True)
            except (ValueError, OSError):
                pass


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
    parser.add_argument(
        "--backtranslation-provider",
        default=os.getenv(
            "AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_PROVIDER", settings.backtranslation_provider
        ),
    )
    parser.add_argument(
        "--backtranslation-model",
        default=os.getenv(
            "AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_MODEL", settings.backtranslation_model
        ),
    )
    parser.add_argument(
        "--judge-provider",
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_JUDGE_PROVIDER", settings.judge_provider),
    )
    parser.add_argument(
        "--judge-model",
        default=os.getenv("AEGIS_OUTPUT_DEFENSE_JUDGE_MODEL", settings.judge_model),
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
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Suppress per-fixture progress lines on stderr",
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


def _progress_line(index: int, total: int, fixture_id: str, label: str, elapsed: float) -> None:
    print(
        f"[{index}/{total}] {fixture_id} ({label}) {elapsed:.1f}s",
        file=sys.stderr,
        flush=True,
    )


async def main() -> int:
    _configure_streaming_output()
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
        backtranslation_router_model=args.backtranslation_model,
        backtranslation_router_provider=args.backtranslation_provider,
        judge_router_model=args.judge_model,
        judge_router_provider=args.judge_provider,
    )
    service = OutputDefenseService(detectors=registry)
    threshold = detection_threshold()

    attacks = sum(1 for f in fixtures if f.is_attack)
    benign = sum(1 for f in fixtures if f.is_benign)

    print("AEGIS Output Defense — Fixture Metrics Report", flush=True)
    print(
        f"Requested backends: toxicity={args.toxicity_backend}, pii={args.pii_backend}, "
        f"backtranslation={args.backtranslation_backend}, judge={args.judge_backend}",
        flush=True,
    )
    if args.backtranslation_backend == "router":
        print(
            f"Router backtranslation: provider={args.backtranslation_provider!r} "
            f"model={args.backtranslation_model!r} timeout={settings.router_timeout}s "
            f"retries={settings.router_max_retries}",
            flush=True,
        )
    print(f"model-router: url={router_url} reachable={router_ok} detail={router_detail!r}", flush=True)
    print(
        f"Scoring {len(fixtures)} fixtures once each ({attacks} attacks, {benign} benign)...",
        flush=True,
    )

    start = time.perf_counter()
    progress = None if args.no_progress else (
        lambda i, total, case, elapsed: _progress_line(i, total, case.id, case.label, elapsed)
    )
    rows = await score_fixtures(service, fixtures, on_progress=progress)
    reports = compute_metrics_from_rows(rows, threshold=threshold)
    category_reports = compute_category_metrics_from_rows(rows, threshold=threshold)
    audit = audit_backend_execution_from_rows(rows, requested=requested, threshold=threshold)
    elapsed = time.perf_counter() - start

    if args.backtranslation_backend == "router" and not router_ok:
        print(
            "WARNING: backtranslation-backend=router but model-router unreachable — "
            "expect stub-fallback-router-error execution paths",
            flush=True,
        )
    print(f"Detection threshold: {threshold:.2f}", flush=True)
    print(f"Scoring time: {elapsed:.1f}s ({elapsed / max(len(fixtures), 1):.1f}s/fixture)", flush=True)
    print(flush=True)
    print(format_backend_audit(audit))
    if args.backtranslation_backend == "router" and attacks:
        sample = next(f for f in fixtures if f.is_attack)
        client = ModelRouterClient(
            router_url,
            model=args.backtranslation_model,
            provider=args.backtranslation_provider,
            timeout=settings.router_timeout,
            max_retries=settings.router_max_retries,
            retry_backoff_seconds=settings.router_retry_backoff_seconds,
        )
        try:
            completion = await client.chat_completion(
                system="You are a semantic analyst.",
                user=sample.content.strip()[:500],
                max_tokens=80,
            )
            print()
            print("-- Sample model-router call (first attack fixture) --")
            print(f"fixture: {sample.id}")
            print(
                f"response provider={completion.provider!r} model={completion.model!r} "
                f"attempted={completion.attempted_providers!r} fallback={completion.fallback_used}"
            )
            print(f"content preview: {completion.content[:200]!r}")
        except Exception as exc:
            print(f"\nSample router call failed: {exc}")
    print()
    print("-- Aggregate --")
    print(format_metrics_table(reports))
    print()
    print("-- ASR by Attack Category --")
    print(format_category_metrics_table(category_reports))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
