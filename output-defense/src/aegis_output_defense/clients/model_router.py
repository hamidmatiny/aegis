"""Async client for model-router chat completions."""

from __future__ import annotations

from typing import Any

import httpx


class ModelRouterClient:
    """Thin wrapper around model-router /v1/chat/completions."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str = "mock-model",
        provider: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._provider = provider
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> str:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._provider:
            body["provider"] = self._provider
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("model-router returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("model-router returned empty content")
        return content.strip()
