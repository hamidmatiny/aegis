"""Fixture loading and metrics computation."""

from __future__ import annotations

from pathlib import Path

import yaml

from aegis_input_defense.fusion import detection_threshold
from aegis_input_defense.models import FixtureCase, MetricsReport
from aegis_input_defense.service import InputDefenseService

FIXTURES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "prompts.yaml"
)


def load_fixtures(path: Path | None = None) -> list[FixtureCase]:
    fixture_path = path or FIXTURES_PATH
    with fixture_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [FixtureCase.model_validate(item) for item in data["fixtures"]]


async def compute_metrics(
    service: InputDefenseService,
    fixtures: list[FixtureCase],
    threshold: float | None = None,
) -> list[MetricsReport]:
    """Compute ASR and FPR per detector and fused pipeline."""
    thresh = threshold if threshold is not None else detection_threshold()
    attacks = [f for f in fixtures if f.is_attack]
    benign = [f for f in fixtures if f.is_benign]

    detector_ids = ["heuristic", "perplexity", "known_answer", "classifier", "fused"]
    reports: list[MetricsReport] = []

    for det_id in detector_ids:
        attack_caught = 0
        false_pos = 0

        for case in attacks:
            if det_id == "fused":
                verdict = await service.analyze_all(case.text.strip())
                score = verdict.fused_score
            else:
                result = await service.analyze_detector(det_id, case.text.strip())
                score = result.score
            if score >= thresh:
                attack_caught += 1

        for case in benign:
            if det_id == "fused":
                verdict = await service.analyze_all(case.text.strip())
                score = verdict.fused_score
            else:
                result = await service.analyze_detector(det_id, case.text.strip())
                score = result.score
            if score >= thresh:
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


def format_metrics_table(reports: list[MetricsReport]) -> str:
    """Render metrics as a markdown table."""
    headers = ["Detector", "Attacks", "Caught", "ASR", "Benign", "FP", "FPR", "Threshold"]
    rows = [[
        r.detector_id,
        str(r.attack_total),
        str(r.attack_caught),
        f"{r.attack_success_rate:.1%}",
        str(r.benign_total),
        str(r.false_positives),
        f"{r.false_positive_rate:.1%}",
        f"{r.threshold:.2f}",
    ] for r in reports]

    col_widths = [max(len(h), max(len(row[i]) for row in rows)) for i, h in enumerate(headers)]

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cells)) + " |"

    sep = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"
    lines = [fmt_row(headers), sep] + [fmt_row(row) for row in rows]
    return "\n".join(lines)
