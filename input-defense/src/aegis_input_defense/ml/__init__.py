"""Shared ML model loading for input-defense detectors."""

from aegis_input_defense.ml.loader import (
    get_perplexity_model,
    get_prompt_guard_model,
    warmup_models,
)

__all__ = [
    "get_perplexity_model",
    "get_prompt_guard_model",
    "warmup_models",
]
