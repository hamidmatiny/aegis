"""Lazy, thread-safe singleton loaders for local ML models."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# unitary/toxic-bert (~110M params, ungated, Apache 2.0) — multi-label toxicity classifier.
TOXIC_BERT_MODEL_ID = "unitary/toxic-bert"
SPACY_MODEL_NAME = "en_core_web_sm"

_toxic_bert_lock = threading.Lock()
_spacy_lock = threading.Lock()
_toxic_bert_cache: dict[str, _ToxicBertBundle] = {}
_spacy_cache: dict[str, Any] = {}


@dataclass(frozen=True)
class _ToxicBertBundle:
    model: Any
    tokenizer: Any
    model_id: str


def get_toxic_bert_model(*, model_id: str = TOXIC_BERT_MODEL_ID) -> _ToxicBertBundle:
    cached = _toxic_bert_cache.get(model_id)
    if cached is not None:
        return cached

    with _toxic_bert_lock:
        cached = _toxic_bert_cache.get(model_id)
        if cached is not None:
            return cached

        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading toxicity model %s", model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSequenceClassification.from_pretrained(model_id)
        model.eval()
        bundle = _ToxicBertBundle(model=model, tokenizer=tokenizer, model_id=model_id)
        _toxic_bert_cache[model_id] = bundle
        return bundle


def get_spacy_nlp(*, model_name: str = SPACY_MODEL_NAME) -> Any:
    cached = _spacy_cache.get(model_name)
    if cached is not None:
        return cached

    with _spacy_lock:
        cached = _spacy_cache.get(model_name)
        if cached is not None:
            return cached

        import spacy

        logger.info("Loading spaCy model %s", model_name)
        try:
            nlp = spacy.load(model_name)
        except OSError as exc:
            raise RuntimeError(
                f"spaCy model {model_name!r} is not installed. "
                f"Run: python -m spacy download {model_name}"
            ) from exc
        _spacy_cache[model_name] = nlp
        return nlp


def warmup_models(
    *,
    toxicity: bool = True,
    pii_ner: bool = True,
    toxic_bert_model_id: str = TOXIC_BERT_MODEL_ID,
    spacy_model: str = SPACY_MODEL_NAME,
) -> None:
    if toxicity:
        get_toxic_bert_model(model_id=toxic_bert_model_id)
    if pii_ner:
        get_spacy_nlp(model_name=spacy_model)


def reset_model_cache_for_tests() -> None:
    with _toxic_bert_lock:
        _toxic_bert_cache.clear()
    with _spacy_lock:
        _spacy_cache.clear()
