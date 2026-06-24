"""Fixture loading and metrics computation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.models import CategoryMetricsReport, FixtureCase, MetricsReport
from aegis_output_defense.service import OutputDefenseService

FIXTURES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "outputs.yaml"
)

DETECTOR_IDS = ["toxicity", "pii", "backtranslation", "fused"]

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


def load_fixtures(path: Path | None = None) -> list[FixtureCase]:
    fixture_path = path or FIXTURES_PATH
    with fixture_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [FixtureCase.model_validate(item) for item in data["fixtures"]]


async def _score_case(
    service: OutputDefenseService,
    case: FixtureCase,
    detector_id: str,
) -> float:
    content = case.content.strip()
    if detector_id == "fused":
        verdict = await service.analyze_all(content, invoke_judge=False)
        return verdict.fused_score
    result = await service.analyze_detector(detector_id, content)
    return result.score


async def compute_metrics(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
) -> list[MetricsReport]:
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


async def compute_category_metrics(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
) -> list[CategoryMetricsReport]:
    thresh = threshold if threshold is not None else detection_threshold()
    attacks_by_category: dict[str, list[FixtureCase]] = defaultdict(list)
    for case in fixtures:
        if case.is_attack:
            attacks_by_category[case.category].append(case)

    categories = sorted(
        attacks_by_category.keys(),
        key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else len(CATEGORY_ORDER), c),
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
                row.append(f"{report.attack_caught}/{report.attack_total} ({report.attack_success_rate:.0%})")
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
