"""Async client for model-router chat completions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ChatCompletionResult:
    content: str
    provider: str
    model: str
    attempted_providers: list[str]
    fallback_used: bool
    raw: dict[str, Any]


class ModelRouterClient:
    """Thin wrapper around model-router /v1/chat/completions."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str = "grok-4.3",
        provider: str = "grok",
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._provider = provider
        self._timeout = timeout
        self._max_retries = max(0, max_retries)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return self._provider

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in {408, 429, 500, 502, 503, 504}

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, httpx.TransportError):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return ModelRouterClient._is_retryable_status(exc.response.status_code)
        return False

    async def chat_completion(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> ChatCompletionResult:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        body: dict[str, Any] = {
            "provider": self._provider,
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_error: Exception | None = None
        timeout = httpx.Timeout(
            connect=10.0,
            read=self._timeout,
            write=10.0,
            pool=10.0,
        )
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self._base_url}/v1/chat/completions",
                        json=body,
                    )
                    response.raise_for_status()
                    payload = response.json()
                break
            except Exception as exc:
                last_error = exc
                if attempt >= self._max_retries or not self._is_retryable_error(exc):
                    raise
                delay = self._retry_backoff_seconds * (2**attempt)
                await asyncio.sleep(delay)
        else:
            assert last_error is not None
            raise last_error

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("model-router returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("model-router returned empty content")

        aegis_meta = payload.get("aegis") or {}
        attempted = aegis_meta.get("attempted_providers") or []
        if not isinstance(attempted, list):
            attempted = []

        return ChatCompletionResult(
            content=content.strip(),
            provider=str(payload.get("provider") or self._provider),
            model=str(payload.get("model") or self._model),
            attempted_providers=[str(p) for p in attempted],
            fallback_used=bool(aegis_meta.get("fallback_used")),
            raw=payload,
        )

    async def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> str:
        return (
            await self.chat_completion(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        ).content
