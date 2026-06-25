"""Real backtranslation consistency via model-router restatement + divergence."""

from __future__ import annotations

import re

from aegis_output_defense.clients.model_router import ModelRouterClient
from aegis_output_defense.detectors.backtranslation.backend import (
    BacktranslationBackend,
    BacktranslationResult,
)
from aegis_output_defense.detectors.backtranslation.stub_backend import StubBacktranslationBackend
from aegis_output_defense.detectors.semantic import divergence_score
from aegis_output_defense.provenance import EXECUTION_BACKEND, FALLBACK_REASON, REQUESTED_BACKEND

_RESTATE_SYSTEM = (
    "You are a semantic analyst. Restate the apparent intent and factual claims of the "
    "user-provided text in one or two neutral sentences. Do not add new information."
)


class RouterBacktranslationBackend(BacktranslationBackend):
    """Semantic smoothing check using model-router restatement."""

    def __init__(
        self,
        client: ModelRouterClient,
        *,
        stub_fallback: BacktranslationBackend | None = None,
    ) -> None:
        self._client = client
        self._stub = stub_fallback or StubBacktranslationBackend()

    @property
    def model_id(self) -> str:
        return f"router-backtranslation/{self._client.model}"

    async def evaluate(
        self,
        content: str,
        *,
        original_prompt: str | None = None,
    ) -> BacktranslationResult:
        try:
            restatement = await self._client.chat(
                system=_RESTATE_SYSTEM,
                user=content[:3000],
                temperature=0.0,
                max_tokens=180,
            )
        except Exception as exc:
            fallback = await self._stub.evaluate(content, original_prompt=original_prompt)
            return BacktranslationResult(
                score=fallback.score,
                reasoning=f"Router unavailable ({exc}); stub fallback: {fallback.reasoning}",
                model_id=self.model_id,
                metadata={
                    REQUESTED_BACKEND: "router",
                    EXECUTION_BACKEND: "stub-fallback-router-error",
                    FALLBACK_REASON: "router-error",
                    "error": str(exc)[:120],
                },
            )

        # Dev mock provider echoes prompts — pattern stub is more reliable there.
        if restatement.startswith("[mock:"):
            fallback = await self._stub.evaluate(content, original_prompt=original_prompt)
            return BacktranslationResult(
                score=fallback.score,
                reasoning=f"Mock router echo; stub fallback: {fallback.reasoning}",
                model_id=self.model_id,
                metadata={
                    REQUESTED_BACKEND: "router",
                    EXECUTION_BACKEND: "stub-fallback-mock-echo",
                    FALLBACK_REASON: "mock-echo",
                    "stub_matches": fallback.metadata.get("matches", ""),
                },
            )

        drift = divergence_score(content, restatement)
        score = 0.05 + 0.90 * drift

        if original_prompt and "do not reveal" in original_prompt.lower():
            if re.search(r"(?i)(api key|password|secret)", content) and not re.search(
                r"(?i)(api key|password|secret)", restatement
            ):
                score = max(score, 0.82)

        reasoning = (
            f"Router restatement divergence {drift:.2f} (score={score:.2f}); "
            f"restatement preview: {restatement[:120]!r}"
        )
        return BacktranslationResult(
            score=min(score, 1.0),
            reasoning=reasoning,
            model_id=self.model_id,
            metadata={
                REQUESTED_BACKEND: "router",
                EXECUTION_BACKEND: "router-live",
                "divergence": f"{drift:.3f}",
                "restatement_chars": str(len(restatement)),
            },
        )
