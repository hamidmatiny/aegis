"""In-process defense stacks for same-corpus campaign comparison."""

from __future__ import annotations

import asyncio
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
        self.router_spend: Any | None = None

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
            )
        return {
            "action": str(verdict.action),
            "fused_score": float(verdict.fused_score),
        }


class _SharedRouterSpend:
    """Single live-call counter shared by backtranslation and judge clients."""

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.calls = 0
        self._lock = asyncio.Lock()


class _SharedSpendClient:
    """ModelRouterClient-compatible proxy that consumes a shared spend budget."""

    def __init__(self, inner: Any, shared: _SharedRouterSpend) -> None:
        self._inner = inner
        self._shared = shared

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def provider(self) -> str:
        return self._inner.provider

    async def chat_completion(self, **kwargs: Any) -> Any:
        from aegis_redteam.probe.router_spend import (
            RouterSpendExhausted,
            looks_like_credit_exhaustion,
            result_looks_like_credit_failure,
        )

        async with self._shared._lock:
            if self._shared.calls >= self._shared.max_calls:
                raise RouterSpendExhausted(
                    f"router call budget exhausted ({self._shared.max_calls} max) "
                    f"after {self._shared.calls} live calls",
                    router_calls=self._shared.calls,
                )
            self._shared.calls += 1
            call_n = self._shared.calls
        try:
            result = await self._inner.chat_completion(**kwargs)
        except Exception as exc:
            if looks_like_credit_exhaustion(exc):
                raise RouterSpendExhausted(
                    f"ran out of credits at router call {call_n}: {exc}",
                    router_calls=call_n,
                ) from exc
            raise
        if result_looks_like_credit_failure(result):
            raise RouterSpendExhausted(
                f"ran out of credits at router call {call_n} (provider={result.provider})",
                router_calls=call_n,
            )
        return result


def build_defense_stack(
    config: DefenseStackConfig,
    *,
    max_router_calls: int | None = None,
) -> LocalDefenseProbe:
    """Construct input/output defense services for the given backend profile.

    When ``max_router_calls`` is set on a router-BT stack, live model-router
    calls are counted and credit/auth failures abort instead of stub-fallback.
    """
    from aegis_input_defense.detectors.registry import (
        build_classifier_backend,
        build_detector_registry,
    )
    from aegis_input_defense.service import InputDefenseService
    from aegis_output_defense.detectors.registry import (
        build_detector_registry as build_out_registry,
    )
    from aegis_output_defense.service import OutputDefenseService

    input_registry = build_detector_registry(
        classifier_backend=build_classifier_backend(config.input_classifier),
        perplexity_backend=config.input_perplexity,
    )

    if config.output_backtranslation == "router" and max_router_calls is not None:
        from aegis_output_defense.clients.model_router import ModelRouterClient
        from aegis_output_defense.detectors.backtranslation.detector import (
            BacktranslationDetector,
        )
        from aegis_output_defense.detectors.backtranslation.router_backend import (
            RouterBacktranslationBackend,
        )
        from aegis_output_defense.detectors.hallucination import HallucinationDetector
        from aegis_output_defense.detectors.judge.detector import JudgeDetector
        from aegis_output_defense.detectors.judge.router_backend import RouterJudgeBackend
        from aegis_output_defense.detectors.pii import PIIDetector
        from aegis_output_defense.detectors.registry import build_toxicity_backend
        from aegis_output_defense.detectors.toxicity.detector import ToxicityDetector
        from aegis_output_defense.settings import settings as out_settings

        shared = _SharedRouterSpend(max_router_calls)
        bt_raw = ModelRouterClient(
            out_settings.model_router_url,
            model=out_settings.backtranslation_model,
            provider=out_settings.backtranslation_provider,
            timeout=out_settings.router_timeout,
            max_retries=out_settings.router_max_retries,
            retry_backoff_seconds=out_settings.router_retry_backoff_seconds,
            token=out_settings.internal_token,
        )
        judge_raw = ModelRouterClient(
            out_settings.model_router_url,
            model=out_settings.judge_model,
            provider=out_settings.judge_provider,
            timeout=out_settings.router_timeout,
            max_retries=out_settings.router_max_retries,
            retry_backoff_seconds=out_settings.router_retry_backoff_seconds,
            token=out_settings.internal_token,
        )
        output_registry = {
            "toxicity": ToxicityDetector(backend=build_toxicity_backend(config.output_toxicity)),
            "pii": PIIDetector(backend=config.output_pii),  # type: ignore[arg-type]
            "hallucination": HallucinationDetector(),
            "backtranslation": BacktranslationDetector(
                backend=RouterBacktranslationBackend(_SharedSpendClient(bt_raw, shared))  # type: ignore[arg-type]
            ),
            "judge": JudgeDetector(
                backend=RouterJudgeBackend(_SharedSpendClient(judge_raw, shared))  # type: ignore[arg-type]
            ),
        }
        probe = LocalDefenseProbe(
            InputDefenseService(detectors=input_registry),
            OutputDefenseService(detectors=output_registry),
        )
        probe.router_spend = shared
        return probe

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
