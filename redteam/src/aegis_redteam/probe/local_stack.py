"""In-process defense stacks for same-corpus campaign comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from aegis_redteam.models import DefenseTarget

DefenseProfile = Literal["stub", "hardened"]


@dataclass
class DefenseStackConfig:
    profile: DefenseProfile
    input_classifier: str
    input_perplexity: str
    output_toxicity: str
    output_pii: str
    output_backtranslation: str


STUB_STACK = DefenseStackConfig(
    profile="stub",
    input_classifier="stub",
    input_perplexity="stub",
    output_toxicity="stub",
    output_pii="regex",
    output_backtranslation="stub",
)

HARDENED_STACK = DefenseStackConfig(
    profile="hardened",
    input_classifier="prompt-guard",
    input_perplexity="lm",
    output_toxicity="toxic-bert",
    output_pii="ner",
    output_backtranslation="router",
)


class LocalDefenseProbe:
    """Score payloads in-process via input/output defense services."""

    def __init__(self, input_service: Any, output_service: Any) -> None:
        self._input = input_service
        self._output = output_service

    async def probe(
        self,
        target: DefenseTarget,
        payload: str,
        *,
        enabled_detectors: list[str] | None = None,
    ) -> dict[str, Any]:
        if target == DefenseTarget.INPUT_DEFENSE:
            verdict = await self._input.analyze_all(
                payload,
                enabled_detectors=enabled_detectors,
            )
        else:
            verdict = await self._output.analyze_all(
                payload,
                enabled_detectors=enabled_detectors,
                invoke_judge=False,
            )
        return {
            "action": str(verdict.action),
            "fused_score": float(verdict.fused_score),
        }


def build_defense_stack(config: DefenseStackConfig) -> LocalDefenseProbe:
    """Construct input/output defense services for the given backend profile."""
    from aegis_input_defense.detectors.registry import (
        build_classifier_backend,
        build_detector_registry,
    )
    from aegis_input_defense.service import InputDefenseService
    from aegis_output_defense.detectors.registry import build_detector_registry as build_out_registry
    from aegis_output_defense.service import OutputDefenseService

    input_registry = build_detector_registry(
        classifier_backend=build_classifier_backend(config.input_classifier),
        perplexity_backend=config.input_perplexity,
    )
    output_registry = build_out_registry(
        toxicity_backend=config.output_toxicity,
        pii_backend=config.output_pii,
        backtranslation_backend=config.output_backtranslation,
    )
    return LocalDefenseProbe(
        InputDefenseService(detectors=input_registry),
        OutputDefenseService(detectors=output_registry),
    )


def warmup_stack(config: DefenseStackConfig) -> None:
    """Pre-load ML models for hardened profiles."""
    if config.profile == "stub":
        return
    from aegis_input_defense.ml.loader import warmup_models as warmup_input
    from aegis_output_defense.ml.loader import warmup_models as warmup_output

    warmup_input(
        prompt_guard=config.input_classifier == "prompt-guard",
        perplexity=config.input_perplexity == "lm",
    )
    warmup_output(
        toxicity=config.output_toxicity == "toxic-bert",
        pii_ner=config.output_pii == "ner",
    )
