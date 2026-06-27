"""Toxic-BERT backend for multi-label toxicity classification."""

from __future__ import annotations

import asyncio

from aegis_output_defense.detectors.toxicity.backend import ToxicityBackend, ToxicityPrediction
from aegis_output_defense.detectors.toxicity.harm_lexicon import score_with_framing_awareness
from aegis_output_defense.ml.loader import TOXIC_BERT_MODEL_ID, get_toxic_bert_model
from aegis_output_defense.provenance import (
    EXECUTION_BACKEND,
    LEXICAL_SCORE,
    ML_SCORE,
    REQUESTED_BACKEND,
    SCORE_SOURCE,
)

_TOXIC_LABELS = ("toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate")


class ToxicBERTBackend(ToxicityBackend):
    """Toxic-BERT plus framing-aware instructional harm lexicon.

    Toxic-BERT generalizes hate/harassment; the instructional harm lexicon catches
    self-harm method content and weapon recipes delivered via fictional/hypothetical
    framing — a documented jailbreak pattern Toxic-BERT often misses.
    """

    def __init__(self, *, model_id: str | None = None) -> None:
        self._model_id = model_id or TOXIC_BERT_MODEL_ID

    @property
    def model_id(self) -> str:
        return self._model_id

    async def predict(self, content: str) -> ToxicityPrediction:
        return await asyncio.to_thread(self._predict_sync, content)

    def _predict_sync(self, content: str) -> ToxicityPrediction:
        ml = self._predict_ml(content)
        instructional, instr_signals, instr_execution = score_with_framing_awareness(content)
        aggregate = max(ml.probability, instructional)
        label = "toxic" if aggregate >= 0.55 else "ambiguous" if aggregate >= 0.30 else "safe"
        reasoning = ml.reasoning
        if instructional > ml.probability:
            reasoning = (
                f"{reasoning}; instructional harm {instructional:.2f} "
                f"({','.join(instr_signals[:4]) or 'none'})"
            )
        if instructional >= aggregate and instructional > ml.probability:
            execution = instr_execution
        elif ml.probability > instructional:
            execution = "toxic-bert-ml"
        else:
            execution = "toxic-bert-ml-low"
        return ToxicityPrediction(
            label=label,
            probability=min(aggregate, 1.0),
            reasoning=reasoning,
            model_id=self.model_id,
            metadata={
                REQUESTED_BACKEND: "toxic-bert",
                EXECUTION_BACKEND: execution,
                SCORE_SOURCE: (
                    f"ml={ml.probability:.4f},instructional={instructional:.4f},"
                    f"aggregate={aggregate:.4f}"
                ),
                ML_SCORE: f"{ml.probability:.6f}",
                LEXICAL_SCORE: f"{instructional:.6f}",
            },
        )

    def _predict_ml(self, content: str) -> ToxicityPrediction:
        bundle = get_toxic_bert_model(model_id=self._model_id)
        text = content[:4000]
        encoded = bundle.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        outputs = bundle.model(**encoded)
        logits = outputs.logits[0]
        probs = logits.sigmoid().tolist()

        label_scores = {
            label: float(prob) for label, prob in zip(_TOXIC_LABELS, probs, strict=True)
        }
        top_label = max(label_scores, key=label_scores.get)  # type: ignore[arg-type]
        score = label_scores[top_label]
        aggregate = max(label_scores.values())
        if aggregate >= 0.55:
            label = "toxic"
        elif aggregate >= 0.30:
            label = "ambiguous"
        else:
            label = "safe"

        fired = [name for name, prob in label_scores.items() if prob >= 0.35]
        reasoning = (
            f"Toxic-BERT: {aggregate:.2f} ({top_label}={score:.2f}); "
            f"signals: {', '.join(fired[:4]) or 'none'}"
        )
        return ToxicityPrediction(
            label=label,
            probability=min(aggregate, 1.0),
            reasoning=reasoning,
            model_id=self.model_id,
        )
