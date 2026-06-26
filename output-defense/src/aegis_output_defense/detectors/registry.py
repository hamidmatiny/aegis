"""Detector registry and factory."""

from __future__ import annotations

from aegis_output_defense.clients.model_router import ModelRouterClient
from aegis_output_defense.detectors.backtranslation.detector import BacktranslationDetector
from aegis_output_defense.detectors.backtranslation.router_backend import (
    RouterBacktranslationBackend,
)
from aegis_output_defense.detectors.backtranslation.stub_backend import StubBacktranslationBackend
from aegis_output_defense.detectors.base import Detector
from aegis_output_defense.detectors.judge.detector import JudgeDetector
from aegis_output_defense.detectors.judge.router_backend import RouterJudgeBackend
from aegis_output_defense.detectors.judge.stub_backend import StubJudgeBackend
from aegis_output_defense.detectors.pii import PIIDetector
from aegis_output_defense.detectors.toxicity.backend import ToxicityBackend
from aegis_output_defense.detectors.toxicity.detector import ToxicityDetector
from aegis_output_defense.settings import settings

ALL_DETECTOR_IDS = ("toxicity", "pii", "backtranslation", "judge")
SCORING_DETECTOR_IDS = ("toxicity", "pii", "backtranslation")
ALWAYS_RUN_IDS = ("toxicity", "pii", "backtranslation")


def build_toxicity_backend(backend: str | None = None) -> ToxicityBackend:
    selected = backend or settings.toxicity_backend
    if selected == "stub":
        from aegis_output_defense.detectors.toxicity.stub_backend import StubToxicityBackend

        return StubToxicityBackend()
    from aegis_output_defense.detectors.toxicity.toxic_bert_backend import ToxicBERTBackend

    return ToxicBERTBackend(model_id=settings.toxic_bert_model_id)


def build_backtranslation_backend(
    backend: str | None = None,
    *,
    router_model: str | None = None,
    router_provider: str | None = None,
) -> StubBacktranslationBackend | RouterBacktranslationBackend:
    selected = backend or settings.backtranslation_backend
    if selected == "stub":
        return StubBacktranslationBackend()
    client = ModelRouterClient(
        settings.model_router_url,
        model=router_model or settings.backtranslation_model,
        provider=router_provider or settings.backtranslation_provider,
        timeout=settings.router_timeout,
        max_retries=settings.router_max_retries,
        retry_backoff_seconds=settings.router_retry_backoff_seconds,
    )
    return RouterBacktranslationBackend(client)


def build_judge_backend(
    backend: str | None = None,
    *,
    router_model: str | None = None,
    router_provider: str | None = None,
) -> StubJudgeBackend | RouterJudgeBackend:
    selected = backend or settings.judge_backend
    if selected == "stub":
        return StubJudgeBackend()
    client = ModelRouterClient(
        settings.model_router_url,
        model=router_model or settings.judge_model,
        provider=router_provider or settings.judge_provider,
        timeout=settings.router_timeout,
        max_retries=settings.router_max_retries,
        retry_backoff_seconds=settings.router_retry_backoff_seconds,
    )
    return RouterJudgeBackend(client)


def build_detector_registry(
    *,
    toxicity_backend: str | None = None,
    pii_backend: str | None = None,
    backtranslation_backend: str | None = None,
    judge_backend: str | None = None,
    backtranslation_router_model: str | None = None,
    backtranslation_router_provider: str | None = None,
    judge_router_model: str | None = None,
    judge_router_provider: str | None = None,
) -> dict[str, Detector]:
    return {
        "toxicity": ToxicityDetector(backend=build_toxicity_backend(toxicity_backend)),
        "pii": PIIDetector(backend=pii_backend or settings.pii_backend),  # type: ignore[arg-type]
        "backtranslation": BacktranslationDetector(
            backend=build_backtranslation_backend(
                backtranslation_backend,
                router_model=backtranslation_router_model,
                router_provider=backtranslation_router_provider,
            ),
        ),
        "judge": JudgeDetector(
            backend=build_judge_backend(
                judge_backend,
                router_model=judge_router_model,
                router_provider=judge_router_provider,
            ),
        ),
    }
