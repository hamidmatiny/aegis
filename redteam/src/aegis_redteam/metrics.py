"""Fixture loading and bypass metrics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from aegis_redteam.models import (
    AttackFixture,
    CampaignReport,
    CategoryBypassMetrics,
    DefenseTarget,
    MetricsReport,
    ProbeResult,
    RoundReport,
    TargetMetrics,
)

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "attacks.yaml"

CATEGORY_ORDER = [
    "direct_injection",
    "roleplay_jailbreak",
    "encoding_obfuscation",
    "leaked_pii",
    "toxic_content",
    "jailbreak_completion",
    "hallucination_incoherent",
]

CATEGORY_LABELS: dict[str, str] = {
    "direct_injection": "direct injection",
    "roleplay_jailbreak": "role-play jailbreak",
    "encoding_obfuscation": "encoding/obfuscation",
    "leaked_pii": "leaked PII/secrets",
    "toxic_content": "toxic/harmful output",
    "jailbreak_completion": "jailbreak completion",
    "hallucination_incoherent": "hallucination/incoherent",
}


def load_fixtures(path: Path | None = None) -> list[AttackFixture]:
    fixture_path = path or FIXTURES_PATH
    with fixture_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [AttackFixture.model_validate(item) for item in data["fixtures"]]


def build_campaign_report(
    campaign_id: str,
    results: list[ProbeResult],
    *,
    threshold: float,
    started_at: datetime,
    completed_at: datetime,
) -> CampaignReport:
    bypasses = [r for r in results if r.bypassed]
    by_target: dict[str, TargetMetrics] = {}
    for target in DefenseTarget:
        target_results = [r for r in results if r.target == target]
        target_bypasses = [r for r in target_results if r.bypassed]
        by_target[target.value] = TargetMetrics(
            target=target.value,
            probes=len(target_results),
            bypasses=len(target_bypasses),
            bypass_rate=len(target_bypasses) / len(target_results) if target_results else 0.0,
        )

    category_map: dict[tuple[str, str], list[ProbeResult]] = defaultdict(list)
    for result in results:
        category_map[(result.category, result.target.value)].append(result)

    categories = sorted(
        category_map.keys(),
        key=lambda k: (
            CATEGORY_ORDER.index(k[0]) if k[0] in CATEGORY_ORDER else len(CATEGORY_ORDER),
            k[0],
        ),
    )
    by_category: list[CategoryBypassMetrics] = []
    for category, target_name in categories:
        rows = category_map[(category, target_name)]
        bypass_count = sum(1 for r in rows if r.bypassed)
        by_category.append(
            CategoryBypassMetrics(
                category=category,
                target=target_name,
                probes=len(rows),
                bypasses=bypass_count,
                bypass_rate=bypass_count / len(rows) if rows else 0.0,
            )
        )

    return CampaignReport(
        campaign_id=campaign_id,
        started_at=started_at,
        completed_at=completed_at,
        results=results,
        threshold=threshold,
        total_probes=len(results),
        bypass_count=len(bypasses),
        bypass_rate=len(bypasses) / len(results) if results else 0.0,
        by_target=by_target,
        by_category=by_category,
    )


def compute_metrics(
    results: list[ProbeResult],
    *,
    threshold: float,
) -> list[MetricsReport]:
    """Aggregate bypass rate (BR) per target and strategy."""
    groups: dict[tuple[str, str], list[ProbeResult]] = defaultdict(list)
    for result in results:
        groups[(result.target.value, result.strategy)].append(result)

    reports: list[MetricsReport] = []
    for (target, strategy), rows in sorted(groups.items()):
        bypass_count = sum(1 for r in rows if r.bypassed)
        reports.append(
            MetricsReport(
                target=target,
                strategy=strategy,
                attack_total=len(rows),
                bypass_count=bypass_count,
                bypass_rate=bypass_count / len(rows) if rows else 0.0,
                threshold=threshold,
            )
        )
    return reports


def format_metrics_table(reports: list[MetricsReport]) -> str:
    headers = ["Target", "Strategy", "Probes", "Bypasses", "BR", "Threshold"]
    rows = [
        [
            r.target,
            r.strategy,
            str(r.attack_total),
            str(r.bypass_count),
            f"{r.bypass_rate:.1%}",
            f"{r.threshold:.2f}",
        ]
        for r in reports
    ]
    return _render_table(headers, rows)


def format_category_table(report: CampaignReport) -> str:
    headers = ["Category", "Target", "N", "Bypasses", "BR"]
    rows = []
    for row in report.by_category:
        label = CATEGORY_LABELS.get(row.category, row.category)
        rows.append(
            [
                label,
                row.target,
                str(row.probes),
                str(row.bypasses),
                f"{row.bypass_rate:.1%}",
            ]
        )
    return _render_table(headers, rows)


def format_round_table(rounds: list[RoundReport]) -> str:
    """Render per-round bypass summary (accepts RoundReport models)."""
    headers = ["Round", "Probes", "Bypasses", "BR", "Variants generated"]
    rows = [
        [
            str(r.round_number),
            str(r.total_probes),
            str(r.bypass_count),
            f"{r.bypass_rate:.1%}",
            str(r.variants_generated),
        ]
        for r in rounds
    ]
    return _render_table(headers, rows)


def format_before_after_table(
    *,
    phase1_bypass_rate: float,
    phase1_probes: int,
    phase1_bypasses: int,
    hardened_bypass_rate: float,
    hardened_probes: int,
    hardened_bypasses: int,
    adaptive_bypass_rate: float,
    adaptive_probes: int,
    adaptive_bypasses: int,
) -> str:
    headers = ["Campaign", "Probes", "Bypasses", "Bypass rate"]
    rows = [
        [
            "Phase 1 stub (same corpus)",
            str(phase1_probes),
            str(phase1_bypasses),
            f"{phase1_bypass_rate:.1%}",
        ],
        [
            "Phase 2 hardened round 1 (same corpus)",
            str(hardened_probes),
            str(hardened_bypasses),
            f"{hardened_bypass_rate:.1%}",
        ],
        [
            "Phase 2 hardened adaptive (rounds 2+)",
            str(adaptive_probes),
            str(adaptive_bypasses),
            f"{adaptive_bypass_rate:.1%}",
        ],
    ]
    return _render_table(headers, rows)


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "(no data)"
    col_widths = [
        max(len(headers[i]), max((len(row[i]) for row in rows), default=0))
        for i in range(len(headers))
    ]

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cells)) + " |"

    sep = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"
    return "\n".join([fmt_row(headers), sep] + [fmt_row(row) for row in rows])
