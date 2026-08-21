"""Hard stop when live model-router spend/credits are exhausted.

Prevents silent stub-fallback mid-campaign so live-BT grades stay honest.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from aegis_output_defense.clients.model_router import ChatCompletionResult, ModelRouterClient

_CREDIT_RE = re.compile(
    r"credits?|spending limit|permission-denied|auth_failed|authentication failed|incorrect api key",
    re.I,
)


class RouterSpendExhausted(Exception):
    """Live router budget hit or provider credits/auth failed — abort campaign."""

    abort_live_bt = True

    def __init__(
        self,
        message: str,
        *,
        router_calls: int | None = None,
        probe_index: int | None = None,
        partial_results: list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.router_calls = router_calls
        self.probe_index = probe_index
        self.partial_results = partial_results or []


def looks_like_credit_exhaustion(exc: BaseException | str) -> bool:
    text = str(exc)
    if _CREDIT_RE.search(text):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403}:
        return True
    return False


def result_looks_like_credit_failure(result: ChatCompletionResult) -> bool:
    aegis = result.raw.get("aegis") or {}
    err = aegis.get("model_error") or {}
    blob = f"{err} {result.provider} {result.content}"
    if err.get("error_type") == "auth_failed":
        return True
    if _CREDIT_RE.search(blob):
        return True
    return False


class SpendGuardedRouterClient:
    """Proxy ModelRouterClient that counts calls and aborts on credit/auth failure."""

    def __init__(self, inner: ModelRouterClient, *, max_calls: int) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        self._inner = inner
        self.max_calls = max_calls
        self.calls = 0
        self._lock = asyncio.Lock()

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def provider(self) -> str:
        return self._inner.provider

    async def chat_completion(self, **kwargs: Any) -> ChatCompletionResult:
        async with self._lock:
            if self.calls >= self.max_calls:
                raise RouterSpendExhausted(
                    f"router call budget exhausted ({self.max_calls} max) "
                    f"after {self.calls} live calls",
                    router_calls=self.calls,
                )
            self.calls += 1
            call_n = self.calls
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
                f"ran out of credits at router call {call_n} "
                f"(provider={result.provider})",
                router_calls=call_n,
            )
        return result

    async def chat(self, **kwargs: Any) -> str:
        return (await self.chat_completion(**kwargs)).content
