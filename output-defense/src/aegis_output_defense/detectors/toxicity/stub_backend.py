"""Lexical stub standing in for a real toxicity/safety classifier."""

from __future__ import annotations

from aegis_output_defense.detectors.toxicity.backend import ToxicityBackend, ToxicityPrediction
from aegis_output_defense.detectors.toxicity.harm_lexicon import score_with_framing_awareness
from aegis_output_defense.provenance import EXECUTION_BACKEND, REQUESTED_BACKEND


class StubToxicityBackend(ToxicityBackend):
    @property
    def model_id(self) -> str:
        return "stub-toxicity-v1"

    async def predict(self, content: str) -> ToxicityPrediction:
        score, fired, execution = score_with_framing_awareness(content)
        if score >= 0.55:
            label = "toxic"
            reasoning = f"Toxicity stub: {score:.2f}; signals: {', '.join(fired[:5]) or 'none'}"
        elif score >= 0.30:
            label = "ambiguous"
            reasoning = f"Toxicity stub: ambiguous {score:.2f}"
        else:
            label = "safe"
            reasoning = f"Toxicity stub: safe ({1 - score:.2f} confidence)"
        return ToxicityPrediction(
            label=label,
            probability=score,
            reasoning=reasoning,
            model_id=self.model_id,
            metadata={
                REQUESTED_BACKEND: "stub",
                EXECUTION_BACKEND: execution,
            },
        )
