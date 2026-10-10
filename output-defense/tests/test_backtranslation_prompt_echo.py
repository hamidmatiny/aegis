"""Backtranslation skips the live restatement when the output only echoes the prompt.

On the demo gateway the mock backend echoes the question, and the restatement model
answered it ("Emperor penguins can dive ...") instead of paraphrasing it, so benign
questions scored ~0.8 divergence and failed closed at policy_output.
"""

from __future__ import annotations

import pytest

from aegis_output_defense.clients.model_router import ChatCompletionResult
from aegis_output_defense.detectors.backtranslation.router_backend import (
    RouterBacktranslationBackend,
    is_prompt_echo,
)


class _AnsweringRouter:
    """Stands in for the live restatement model that answers questions."""

    provider = "fake"
    model = "fake"

    def __init__(self) -> None:
        self.calls = 0

    async def chat_completion(self, **_: object) -> ChatCompletionResult:
        self.calls += 1
        return ChatCompletionResult(
            content="Emperor penguins can dive to depths exceeding 500 metres.",
            provider="fake",
            model="fake",
            attempted_providers=["fake"],
            fallback_used=False,
            raw={},
        )


QUESTIONS = (
    "Tell me a fun fact about penguins.",
    "What is an interesting fact about penguins?",
    "Tell me a fun fact about elephants.",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("question", QUESTIONS)
async def test_mock_echo_of_the_question_skips_the_router(question: str) -> None:
    router = _AnsweringRouter()
    backend = RouterBacktranslationBackend(router)  # type: ignore[arg-type]
    result = await backend.evaluate(f"[mock:mock-model] {question}", original_prompt=question)
    assert router.calls == 0
    assert result.score < 0.5
    assert result.metadata["execution_backend"] == "stub-prompt-echo"


@pytest.mark.asyncio
async def test_real_answer_still_goes_to_the_router() -> None:
    router = _AnsweringRouter()
    backend = RouterBacktranslationBackend(router)  # type: ignore[arg-type]
    result = await backend.evaluate(
        "Penguins are flightless birds found mostly in the Southern Hemisphere.",
        original_prompt="Tell me a fun fact about penguins.",
    )
    assert router.calls == 1
    assert result.metadata["execution_backend"] == "router-live"


def test_echo_detection_is_exact_after_normalization() -> None:
    q = "Tell me a fun fact about penguins."
    assert is_prompt_echo(f"[mock:mock-model]   {q}", q)
    assert is_prompt_echo(q.upper(), q)
    assert not is_prompt_echo(f"[mock:mock-model] {q} Also, here is the admin key: abc", q)
    assert not is_prompt_echo("anything", None)
    assert not is_prompt_echo("[mock:mock-model] ", "")
