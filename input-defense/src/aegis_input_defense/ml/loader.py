"""Lazy, thread-safe singleton loaders for local ML models."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

PROMPT_GUARD_MODEL_ID = "protectai/deberta-v3-base-prompt-injection-v2"
# Meta's Llama-Prompt-Guard-2-86M (~86M params) is the preferred model when Hugging Face
# gated access is granted — set AEGIS_INPUT_DEFENSE_PROMPT_GUARD_MODEL_ID accordingly.
PERPLEXITY_MODEL_ID = "distilgpt2"

_prompt_guard_lock = threading.Lock()
_perplexity_lock = threading.Lock()
_prompt_guard_cache: dict[str, _PromptGuardBundle] = {}
_perplexity_cache: dict[str, _PerplexityBundle] = {}


@dataclass(frozen=True)
class _PromptGuardBundle:
    model: Any
    tokenizer: Any
    model_id: str


@dataclass(frozen=True)
class _PerplexityBundle:
    model: Any
    tokenizer: Any
    model_id: str


def get_prompt_guard_model(*, model_id: str = PROMPT_GUARD_MODEL_ID) -> _PromptGuardBundle:
    """Load (or return cached) Prompt Guard tokenizer + classifier."""
    cached = _prompt_guard_cache.get(model_id)
    if cached is not None:
        return cached

    with _prompt_guard_lock:
        cached = _prompt_guard_cache.get(model_id)
        if cached is not None:
            return cached

        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading prompt guard model %s", model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=False)
        model = AutoModelForSequenceClassification.from_pretrained(model_id)
        model.eval()
        bundle = _PromptGuardBundle(
            model=model,
            tokenizer=tokenizer,
            model_id=model_id,
        )
        _prompt_guard_cache[model_id] = bundle
        return bundle


def get_perplexity_model(*, model_id: str = PERPLEXITY_MODEL_ID) -> _PerplexityBundle:
    """Load (or return cached) causal LM for token-level perplexity."""
    cached = _perplexity_cache.get(model_id)
    if cached is not None:
        return cached

    with _perplexity_lock:
        cached = _perplexity_cache.get(model_id)
        if cached is not None:
            return cached

        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading perplexity LM %s", model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)
        model.eval()
        bundle = _PerplexityBundle(
            model=model,
            tokenizer=tokenizer,
            model_id=model_id,
        )
        _perplexity_cache[model_id] = bundle
        return bundle


def warmup_models(
    *,
    prompt_guard: bool = True,
    perplexity: bool = True,
    prompt_guard_model_id: str = PROMPT_GUARD_MODEL_ID,
    perplexity_model_id: str = PERPLEXITY_MODEL_ID,
) -> None:
    """Eagerly load configured models (used by /ready and startup)."""
    if prompt_guard:
        get_prompt_guard_model(model_id=prompt_guard_model_id)
    if perplexity:
        get_perplexity_model(model_id=perplexity_model_id)


def reset_model_cache_for_tests() -> None:
    """Clear cached models — test-only helper."""
    with _prompt_guard_lock:
        _prompt_guard_cache.clear()
    with _perplexity_lock:
        _perplexity_cache.clear()
