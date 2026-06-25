"""Token-level perplexity helpers using a causal language model."""

from __future__ import annotations

import math

from aegis_input_defense.ml.loader import PERPLEXITY_MODEL_ID, get_perplexity_model

_TOKEN_WINDOW = 48
_TOKEN_STEP = 24


def token_sequence_perplexity(text: str, *, model_id: str = PERPLEXITY_MODEL_ID) -> float:
    """
    Compute token-level perplexity with a causal LM (DistilGPT2 by default).

    Returns 1.0 for empty/too-short segments.
    """
    normalized = text.strip()
    if len(normalized) < 4:
        return 1.0

    import torch
    import torch.nn.functional as F

    bundle = get_perplexity_model(model_id=model_id)
    inputs = bundle.tokenizer(
        normalized,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    input_ids = inputs["input_ids"]
    if input_ids.shape[1] < 2:
        return 1.0

    with torch.no_grad():
        outputs = bundle.model(input_ids=input_ids)
        logits = outputs.logits[:, :-1, :]
        labels = input_ids[:, 1:]
        loss = F.cross_entropy(
            logits.reshape(-1, logits.size(-1)),
            labels.reshape(-1),
        )
    ppl = math.exp(float(loss.item()))
    return max(ppl, 1.0)


def token_window_segments(text: str, *, model_id: str = PERPLEXITY_MODEL_ID) -> list[str]:
    """Split text into overlapping token windows for local anomaly scoring."""
    bundle = get_perplexity_model(model_id=model_id)
    token_ids = bundle.tokenizer.encode(text, truncation=True, max_length=512)
    if len(token_ids) <= _TOKEN_WINDOW:
        return [text]

    segments: list[str] = []
    for start in range(0, len(token_ids) - _TOKEN_WINDOW + 1, _TOKEN_STEP):
        chunk_ids = token_ids[start : start + _TOKEN_WINDOW]
        segments.append(bundle.tokenizer.decode(chunk_ids))
    return segments
