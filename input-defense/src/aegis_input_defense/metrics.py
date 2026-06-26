"""Fixture loading and metrics computation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

from aegis_input_defense.detectors.registry import ALL_DETECTOR_IDS
from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.models import (
    AblationMetricsReport,
    CategoryMetricsReport,
    FixtureCase,
    MetricsReport,
)
from aegis_input_defense.service import InputDefenseService

FIXTURES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "prompts.yaml"
)

DETECTOR_IDS = ["heuristic", "perplexity", "known_answer", "classifier", "fused"]

ABLATION_OMIT_IDS = ["heuristic", "perplexity", "known_answer", "classifier"]

# Stable display order for category breakdown tables
CATEGORY_ORDER = [
    "direct_injection",
    "roleplay_jailbreak",
    "encoding_obfuscation",
    "indirect_injection",
    "multi_turn_escalation",
]

CATEGORY_LABELS: dict[str, str] = {
    "direct_injection": "direct injection",
    "roleplay_jailbreak": "role-play",
    "encoding_obfuscation": "encoding/obfuscation",
    "indirect_injection": "indirect injection",
    "multi_turn_escalation": "multi-turn",
}


def load_fixtures(path: Path | None = None) -> list[FixtureCase]:
    fixture_path = path or FIXTURES_PATH
    with fixture_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [FixtureCase.model_validate(item) for item in data["fixtures"]]


async def _score_case(
    service: InputDefenseService,
    case: FixtureCase,
    detector_id: str,
) -> float:
    text = case.text.strip()
    if detector_id == "fused":
        verdict = await service.analyze_all(text)
        return verdict.fused_score
    result = await service.analyze_detector(detector_id, text)
    return result.score


async def compute_metrics(
    service: InputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
) -> list[MetricsReport]:
    """Compute aggregate ASR and FPR per detector and fused pipeline."""
    thresh = threshold if threshold is not None else detection_threshold()
    attacks = [f for f in fixtures if f.is_attack]
    benign = [f for f in fixtures if f.is_benign]

    reports: list[MetricsReport] = []

    for det_id in DETECTOR_IDS:
        attack_caught = 0
        false_pos = 0

        for case in attacks:
            if (await _score_case(service, case, det_id)) >= thresh:
                attack_caught += 1

        for case in benign:
            if (await _score_case(service, case, det_id)) >= thresh:
                false_pos += 1

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
    service: InputDefenseService,
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
        verdict = await service.analyze_all(case.text.strip(), enabled_detectors=enabled_detectors)
        if verdict.fused_score >= threshold:
            attack_caught += 1
    for case in benign:
        verdict = await service.analyze_all(case.text.strip(), enabled_detectors=enabled_detectors)
        if verdict.fused_score >= threshold:
            false_pos += 1
    asr = attack_caught / len(attacks) if attacks else 0.0
    fpr = false_pos / len(benign) if benign else 0.0
    return asr, fpr


async def compute_ablation_metrics(
    service: InputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
) -> list[AblationMetricsReport]:
    """Fused ASR/FPR with each scoring detector removed one at a time."""
    thresh = threshold if threshold is not None else detection_threshold()
    full_enabled = list(ALL_DETECTOR_IDS)
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
        enabled = [d for d in ALL_DETECTOR_IDS if d != omit]
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


async def compute_category_metrics(
    service: InputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
) -> list[CategoryMetricsReport]:
    """Compute ASR per attack category for each detector and the fused pipeline."""
    thresh = threshold if threshold is not None else detection_threshold()
    attacks_by_category: dict[str, list[FixtureCase]] = defaultdict(list)
    for case in fixtures:
        if case.is_attack:
            attacks_by_category[case.category].append(case)

    categories = sorted(
        attacks_by_category.keys(),
        key=lambda c: (
            CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else len(CATEGORY_ORDER),
            c,
        ),
    )

    reports: list[CategoryMetricsReport] = []
    for category in categories:
        cases = attacks_by_category[category]
        for det_id in DETECTOR_IDS:
            caught = 0
            for case in cases:
                if (await _score_case(service, case, det_id)) >= thresh:
                    caught += 1
            reports.append(
                CategoryMetricsReport(
                    category=category,
                    detector_id=det_id,
                    attack_total=len(cases),
                    attack_caught=caught,
                    attack_success_rate=caught / len(cases) if cases else 0.0,
                    threshold=thresh,
                )
            )

    return reports


def format_metrics_table(reports: list[MetricsReport]) -> str:
    """Render aggregate metrics as a markdown table."""
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
    """
    Render category ASR as a pivot table.

    Rows = attack categories; columns = detectors + fused.
    """
    if not reports:
        return "(no attack fixtures)"

    categories = []
    seen: set[str] = set()
    for r in reports:
        if r.category not in seen:
            seen.add(r.category)
            categories.append(r.category)

    categories.sort(
        key=lambda c: (
            CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else len(CATEGORY_ORDER),
            c,
        )
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
                caught = report.attack_caught
                total = report.attack_total
                rate = report.attack_success_rate
                row.append(f"{caught}/{total} ({rate:.0%})")
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
