"""Fixture backend execution audit for metrics reports."""

from __future__ import annotations

from collections import Counter

from aegis_output_defense.fusion import detection_threshold
from aegis_output_defense.models import FixtureCase
from aegis_output_defense.provenance import (
    EXECUTION_BACKEND,
    FALLBACK_REASON,
    LEXICAL_SCORE,
    ML_SCORE,
    NER_CHANGED_SCORE,
    BackendAuditSummary,
)
from aegis_output_defense.service import OutputDefenseService


async def audit_backend_execution(
    service: OutputDefenseService,
    fixtures: list[FixtureCase],
    *,
    requested: dict[str, str],
    threshold: float | None = None,
) -> list[BackendAuditSummary]:
    """Summarize which backend path actually ran for each detector across fixtures."""
    thresh = threshold if threshold is not None else detection_threshold()
    summaries: list[BackendAuditSummary] = []

    for detector_id in ("toxicity", "pii", "backtranslation"):
        counts: Counter[str] = Counter()
        fallbacks = 0
        ml_outcome_changes = 0
        ner_outcome_changes = 0

        for case in fixtures:
            content = case.content.strip()
            result = await service.analyze_detector(detector_id, content)
            meta = result.metadata
            execution = meta.get(EXECUTION_BACKEND, "unknown")
            counts[execution] += 1
            if meta.get(FALLBACK_REASON):
                fallbacks += 1

            if detector_id == "toxicity":
                ml = meta.get(ML_SCORE)
                lex = meta.get(LEXICAL_SCORE)
                if ml is not None and lex is not None:
                    ml_fires = float(ml) >= thresh
                    lex_fires = float(lex) >= thresh
                    if ml_fires != lex_fires:
                        ml_outcome_changes += 1

            if detector_id == "pii" and meta.get(NER_CHANGED_SCORE) == "true":
                ner_outcome_changes += 1

        summaries.append(
            BackendAuditSummary(
                detector_id=detector_id,
                requested_backend=requested.get(detector_id, "unknown"),
                execution_counts=counts,
                fallback_count=fallbacks,
                fixtures_where_ml_changed_outcome=ml_outcome_changes,
                fixtures_where_ner_changed_outcome=ner_outcome_changes,
            )
        )

    return summaries
