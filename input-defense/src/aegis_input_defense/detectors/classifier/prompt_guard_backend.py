"""Llama-Prompt-Guard-2-86M classifier backend (local transformers)."""

from __future__ import annotations

import asyncio
from typing import Any

from aegis_input_defense.detectors.classifier.backend import ClassifierBackend, ClassifierPrediction
from aegis_input_defense.ml.loader import PROMPT_GUARD_MODEL_ID, get_prompt_guard_model

_MAX_CHARS = 2048
_CHUNK_CHARS = 1800  # conservative char budget for 512-token windows


def _injection_class_index(id2label: dict[int, str]) -> int:
    """Resolve which logit index corresponds to injection/malicious."""
    normalized = {int(k): str(v).upper() for k, v in id2label.items()}
    injection_keywords = ("INJECTION", "MALICIOUS", "JAILBREAK", "ATTACK", "UNSAFE")
    benign_keywords = ("SAFE", "BENIGN", "LEGIT", "NON_INJECTION", "NOT_INJECTION")

    for idx, label in normalized.items():
        if any(keyword in label for keyword in injection_keywords):
            return idx

    for idx, label in normalized.items():
        if any(keyword in label for keyword in benign_keywords):
            others = [i for i in normalized if i != idx]
            if len(others) == 1:
                return others[0]

    # Fallback: binary classifier convention used by several public checkpoints.
    if 1 in normalized and normalized[1] == "LABEL_1":
        return 1
    return max(normalized)


def _segment_probability(model: Any, tokenizer: Any, segment: str) -> tuple[float, str]:
    import torch

    inputs = tokenizer(
        segment,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    with torch.no_grad():
        logits = model(**inputs).logits

    probs = torch.softmax(logits, dim=-1)[0]
    id2label = {int(k): str(v) for k, v in model.config.id2label.items()}
    injection_idx = _injection_class_index(id2label)

    score = float(probs[injection_idx].item())
    label_name = id2label.get(injection_idx, "injection").lower()
    return score, label_name


def _predict_sync(text: str, *, model_id: str) -> ClassifierPrediction:
    bundle = get_prompt_guard_model(model_id=model_id)
    normalized = text.strip()
    if not normalized:
        return ClassifierPrediction(
            label="benign",
            probability=0.0,
            reasoning="Empty input",
            model_id=bundle.model_id,
        )

    segments = _split_segments(normalized)
    segment_scores: list[float] = []

    for segment in segments:
        score, _label = _segment_probability(bundle.model, bundle.tokenizer, segment)
        segment_scores.append(score)

    probability = max(segment_scores)
    if probability >= 0.55:
        label = "injection"
    elif probability >= 0.35:
        label = "ambiguous"
    else:
        label = "benign"

    if len(segments) == 1:
        reasoning = f"Prompt Guard: {label} probability {probability:.3f} (model={bundle.model_id})"
    else:
        reasoning = (
            f"Prompt Guard: max segment probability {probability:.3f} across "
            f"{len(segments)} windows (model={bundle.model_id})"
        )

    return ClassifierPrediction(
        label=label,
        probability=probability,
        reasoning=reasoning,
        model_id=bundle.model_id,
    )


def _split_segments(text: str) -> list[str]:
    if len(text) <= _MAX_CHARS:
        return [text]

    segments: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_CHARS, len(text))
        segments.append(text[start:end])
        if end >= len(text):
            break
        start = end
    return segments


class PromptGuardBackend(ClassifierBackend):
    """
    Local prompt-injection classifier via Hugging Face transformers.

    Default model: neuralchemy/prompt-injection-deberta (DeBERTa-v3-small, ~44M params,
    Apache 2.0, ungated) for clone-and-run reproducibility without Hugging Face approvals.

    For Meta's Llama-Prompt-Guard-2-86M (~86M params), set
    AEGIS_INPUT_DEFENSE_PROMPT_GUARD_MODEL_ID=meta-llama/Llama-Prompt-Guard-2-86M
    (requires Hugging Face gated access + HF_TOKEN/HUGGINGFACE_HUB_TOKEN).
    """

    def __init__(self, *, model_id: str = PROMPT_GUARD_MODEL_ID) -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    async def predict(self, text: str) -> ClassifierPrediction:
        return await asyncio.to_thread(_predict_sync, text, model_id=self._model_id)
