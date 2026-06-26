"""Fixture loading and metrics computation."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import yaml

from aegis_output_defense.detectors.registry import ALWAYS_RUN_IDS
from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.models import (
    AblationMetricsReport,
    CategoryMetricsReport,
    FixtureCase,
    FixtureScoreRow,
    MetricsReport,
)
from aegis_output_defense.service import OutputDefenseService

FIXTURES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "outputs.yaml"
)

DETECTOR_IDS = ["toxicity", "pii", "backtranslation", "fused"]

ABLATION_OMIT_IDS = ["toxicity", "pii", "backtranslation"]

CATEGORY_ORDER = [
    "leaked_pii",
    "toxic_content",
    "jailbreak_completion",
    "hallucination_incoherent",
]

CATEGORY_LABELS: dict[str, str] = {
    "leaked_pii": "leaked PII/secrets",
    "toxic_content": "toxic/harmful",
    "jailbreak_completion": "jailbreak success",
    "hallucination_incoherent": "hallucination/incoherent",
}

ProgressCallback = Callable[[int, int, FixtureCase, float], None]


def load_fixtures(path: Path | None = None) -> list[FixtureCase]:
    fixture_path = path or FIXTURES_PATH
    with fixture_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [FixtureCase.model_validate(item) for item in data["fixtures"]]


async def score_fixtures(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    *,
    on_progress: ProgressCallback | None = None,
) -> list[FixtureScoreRow]:
    """Score each fixture once via analyze_all (one router call per fixture when enabled)."""
    rows: list[FixtureScoreRow] = []
    total = len(fixtures)
    for index, case in enumerate(fixtures, start=1):
        started = time.perf_counter()
        verdict = await service.analyze_all(case.content.strip(), invoke_judge=False)
        elapsed = time.perf_counter() - started

        scores = {entry.detector_id: entry.score for entry in verdict.detector_scores}
        scores["fused"] = verdict.fused_score
        metadata = {entry.detector_id: dict(entry.metadata) for entry in verdict.detector_scores}

        rows.append(
            FixtureScoreRow(
                case=case,
                scores=scores,
                metadata=metadata,
            )
        )
        if on_progress is not None:
            on_progress(index, total, case, elapsed)
    return rows


def compute_metrics_from_rows(
    rows: list[FixtureScoreRow],
    threshold: float | None = None,
) -> list[MetricsReport]:
    thresh = threshold if threshold is not None else detection_threshold()
    attacks = [row for row in rows if row.case.is_attack]
    benign = [row for row in rows if row.case.is_benign]
    reports: list[MetricsReport] = []

    for det_id in DETECTOR_IDS:
        attack_caught = sum(1 for row in attacks if row.scores.get(det_id, 0.0) >= thresh)
        false_pos = sum(1 for row in benign if row.scores.get(det_id, 0.0) >= thresh)
        reports.append(
            MetricsReport(
                detector_id=det_id,
                attack_total=len(attacks),
                attack_caught=attack_caught,
                attack_success_rate=attack_caught / len(attacks) if attacks else 0.0,
                benign_total=len(benign),
                false_positives=false_pos,
                false_positive_rate=false_pos / len(benign) if benign else 0.0,
                threshold=thresh,
            )
        )
    return reports


async def _fused_rates(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    *,
    enabled_detectors: list[str],
    threshold: float,
) -> tuple[float, float]:
    attacks = [f for f in fixtures if f.is_attack]
    benign = [f for f in fixtures if f.is_benign]
    attack_caught = 0
    false_pos = 0
    for case in attacks:
        verdict = await service.analyze_all(
            case.content.strip(),
            enabled_detectors=enabled_detectors,
            invoke_judge=False,
        )
        if verdict.fused_score >= threshold:
            attack_caught += 1
    for case in benign:
        verdict = await service.analyze_all(
            case.content.strip(),
            enabled_detectors=enabled_detectors,
            invoke_judge=False,
        )
        if verdict.fused_score >= threshold:
            false_pos += 1
    asr = attack_caught / len(attacks) if attacks else 0.0
    fpr = false_pos / len(benign) if benign else 0.0
    return asr, fpr


async def compute_ablation_metrics(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
) -> list[AblationMetricsReport]:
    thresh = threshold if threshold is not None else detection_threshold()
    full_enabled = list(ALWAYS_RUN_IDS)
    full_asr, full_fpr = await _fused_rates(
        service, fixtures, enabled_detectors=full_enabled, threshold=thresh
    )

    reports: list[AblationMetricsReport] = [
        AblationMetricsReport(
            omitted_detector="(none — full ensemble)",
            attack_success_rate=full_asr,
            false_positive_rate=full_fpr,
            delta_asr=0.0,
            delta_fpr=0.0,
            threshold=thresh,
        )
    ]

    for omit in ABLATION_OMIT_IDS:
        enabled = [d for d in ALWAYS_RUN_IDS if d != omit]
        asr, fpr = await _fused_rates(
            service, fixtures, enabled_detectors=enabled, threshold=thresh
        )
        reports.append(
            AblationMetricsReport(
                omitted_detector=omit,
                attack_success_rate=asr,
                false_positive_rate=fpr,
                delta_asr=full_asr - asr,
                delta_fpr=full_fpr - fpr,
                threshold=thresh,
            )
        )
    return reports


def format_ablation_table(reports: list[AblationMetricsReport]) -> str:
    headers = [
        "Omitted detector",
        "Fused ASR",
        "Fused FPR",
        "Δ ASR vs full",
        "Δ FPR vs full",
    ]
    rows = [
        [
            r.omitted_detector,
            f"{r.attack_success_rate:.1%}",
            f"{r.false_positive_rate:.1%}",
            f"{r.delta_asr:+.1%}",
            f"{r.delta_fpr:+.1%}",
        ]
        for r in reports
    ]
    return _render_table(headers, rows)


def compute_category_metrics_from_rows(
    rows: list[FixtureScoreRow],
    threshold: float | None = None,
) -> list[CategoryMetricsReport]:
    thresh = threshold if threshold is not None else detection_threshold()
    attacks_by_category: dict[str, list[FixtureScoreRow]] = defaultdict(list)
    for row in rows:
        if row.case.is_attack:
            attacks_by_category[row.case.category].append(row)

    categories = sorted(
        attacks_by_category.keys(),
        key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else len(CATEGORY_ORDER), c),
    )

    reports: list[CategoryMetricsReport] = []
    for category in categories:
        category_rows = attacks_by_category[category]
        for det_id in DETECTOR_IDS:
            caught = sum(1 for row in category_rows if row.scores.get(det_id, 0.0) >= thresh)
            reports.append(
                CategoryMetricsReport(
                    category=category,
                    detector_id=det_id,
                    attack_total=len(category_rows),
                    attack_caught=caught,
                    attack_success_rate=caught / len(category_rows) if category_rows else 0.0,
                    threshold=thresh,
                )
            )
    return reports


async def compute_metrics(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
    *,
    rows: list[FixtureScoreRow] | None = None,
) -> list[MetricsReport]:
    scored = rows if rows is not None else await score_fixtures(service, fixtures)
    return compute_metrics_from_rows(scored, threshold)


async def compute_category_metrics(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
    *,
    rows: list[FixtureScoreRow] | None = None,
) -> list[CategoryMetricsReport]:
    scored = rows if rows is not None else await score_fixtures(service, fixtures)
    return compute_category_metrics_from_rows(scored, threshold)


def format_metrics_table(reports: list[MetricsReport]) -> str:
    headers = ["Detector", "Attacks", "Caught", "ASR", "Benign", "FP", "FPR", "Threshold"]
    rows = [
        [
            r.detector_id,
            str(r.attack_total),
            str(r.attack_caught),
            f"{r.attack_success_rate:.1%}",
            str(r.benign_total),
            str(r.false_positives),
            f"{r.false_positive_rate:.1%}",
            f"{r.threshold:.2f}",
        ]
        for r in reports
    ]
    return _render_table(headers, rows)


def format_category_metrics_table(reports: list[CategoryMetricsReport]) -> str:
    if not reports:
        return "(no attack fixtures)"
    categories = []
    seen: set[str] = set()
    for r in reports:
        if r.category not in seen:
            seen.add(r.category)
            categories.append(r.category)
    categories.sort(
        key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else len(CATEGORY_ORDER), c)
    )
    lookup = {(r.category, r.detector_id): r for r in reports}
    headers = ["Category", "N"] + DETECTOR_IDS
    rows: list[list[str]] = []
    for category in categories:
        n = next(r.attack_total for r in reports if r.category == category)
        label = CATEGORY_LABELS.get(category, category)
        row = [label, str(n)]
        for det_id in DETECTOR_IDS:
            report = lookup.get((category, det_id))
            if report is None:
                row.append("—")
            else:
                rate = report.attack_success_rate
                row.append(f"{report.attack_caught}/{report.attack_total} ({rate:.0%})")
        rows.append(row)
    return _render_table(headers, rows)


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    col_widths = [
        max(len(headers[i]), max((len(row[i]) for row in rows), default=0))
        for i in range(len(headers))
    ]

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cells)) + " |"

    sep = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"
    return "\n".join([fmt_row(headers), sep] + [fmt_row(row) for row in rows])
