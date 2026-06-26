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
    "Paraphrase the assistant output in your own words while preserving the exact meaning. "
    "Output only the paraphrase — no preamble, no meta-commentary (never write "
    "'The text states' or 'The speaker'), and do not wrap the original in quotes. "
    "Keep technical terms, numbers, and named entities when present."
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
        return f"router-backtranslation/{self._client.provider}/{self._client.model}"

    async def evaluate(
        self,
        content: str,
        *,
        original_prompt: str | None = None,
    ) -> BacktranslationResult:
        try:
            completion = await self._client.chat_completion(
                system=_RESTATE_SYSTEM,
                user=content[:3000],
                temperature=0.0,
                max_tokens=180,
            )
            restatement = completion.content
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

        # Mock echo means model-router exhausted the fallback chain (often content-policy
        # refusals on all real providers, not a transient network blip).
        if restatement.startswith("[mock:") or completion.provider == "mock":
            fallback = await self._stub.evaluate(content, original_prompt=original_prompt)
            reason = "provider-chain-mock-echo"
            if completion.fallback_used and completion.attempted_providers:
                reason = "provider-chain-exhausted-mock-echo"
            return BacktranslationResult(
                score=fallback.score,
                reasoning=(
                    f"Model-router fell back to mock echo "
                    f"(attempted={completion.attempted_providers}); stub fallback: {fallback.reasoning}"
                ),
                model_id=self.model_id,
                metadata={
                    REQUESTED_BACKEND: "router",
                    EXECUTION_BACKEND: "stub-fallback-mock-echo",
                    FALLBACK_REASON: reason,
                    "router_provider": completion.provider,
                    "router_model": completion.model,
                    "attempted_providers": ",".join(completion.attempted_providers),
                    "fallback_used": str(completion.fallback_used),
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
                "router_provider": completion.provider,
                "router_model": completion.model,
                "attempted_providers": ",".join(completion.attempted_providers),
                "divergence": f"{drift:.3f}",
                "restatement_chars": str(len(restatement)),
            },
        )
