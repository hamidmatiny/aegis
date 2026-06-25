"""Standard keys for backend execution provenance in detector metadata."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

EXECUTION_BACKEND = "execution_backend"
REQUESTED_BACKEND = "requested_backend"
SCORE_SOURCE = "score_source"
FALLBACK_REASON = "fallback_reason"
ML_SCORE = "ml_score"
LEXICAL_SCORE = "lexical_score"
REGEX_MATCHES = "regex_matches"
NER_MATCHES = "ner_matches"
NER_CHANGED_SCORE = "ner_changed_score"


@dataclass
class BackendAuditSummary:
    detector_id: str
    requested_backend: str
    execution_counts: Counter[str] = field(default_factory=Counter)
    fallback_count: int = 0
    fixtures_where_ner_changed_outcome: int = 0
    fixtures_where_ml_changed_outcome: int = 0

    def lines(self) -> list[str]:
        total = sum(self.execution_counts.values())
        rows = [
            f"  {self.detector_id}: requested={self.requested_backend!r}",
        ]
        for path, count in sorted(self.execution_counts.items()):
            rows.append(f"    execution_backend={path!r}: {count}/{total} fixtures")
        if self.fallback_count:
            rows.append(f"    fallbacks: {self.fallback_count}/{total}")
        if self.detector_id == "pii" and self.fixtures_where_ner_changed_outcome == 0:
            rows.append(
                "    NER changed threshold outcome on 0 fixtures "
                "(regex sufficient on this set)"
            )
        if (
            self.detector_id == "toxicity"
            and self.requested_backend == "toxic-bert"
            and self.fixtures_where_ml_changed_outcome == 0
        ):
            rows.append(
                "    Toxic-BERT ML alone changed threshold outcome on 0 fixtures "
                "(lexical calibration dominates catches on this set)"
            )
        return rows


def format_backend_audit(summaries: list[BackendAuditSummary]) -> str:
    lines = ["-- Backend execution audit (requested vs actual) --"]
    for summary in summaries:
        lines.extend(summary.lines())
    return "\n".join(lines)
