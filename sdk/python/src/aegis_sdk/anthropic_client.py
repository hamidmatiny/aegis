"""Anthropic-compatible messages client backed by AEGIS."""

from __future__ import annotations

from typing import Any

from aegis_sdk.openai_client import OpenAI
from aegis_sdk.settings import settings


class _Messages:
    def __init__(self, client: Anthropic) -> None:
        self._client = client

    def create(self, **kwargs: Any) -> dict[str, Any]:
        return self._client._create_message(**kwargs)


class Anthropic:
    """Thin wrapper mapping Anthropic ``messages.create`` to AEGIS chat pipeline."""

    def __init__(self, **kwargs: Any) -> None:
        self._openai = OpenAI(**kwargs)
        self.messages = _Messages(self)

    def _create_message(self, **kwargs: Any) -> dict[str, Any]:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._create_message_async(**kwargs))
        raise RuntimeError("messages.create() cannot be called from an async context")

    async def _create_message_async(self, **kwargs: Any) -> dict[str, Any]:
        messages = self._to_openai_messages(kwargs.get("messages") or [])
        model = kwargs.get("model") or settings.default_model
        max_tokens = kwargs.get("max_tokens")

        if self._openai.base_url:
            # Proxy mode: use Anthropic route when available, else OpenAI route.
            raise NotImplementedError(
                "Anthropic proxy route is not exposed yet; "
                "use OpenAI base_url or embedded OpenAI client"
            )

        resp = await self._openai._create_completion_async(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=kwargs.get("temperature"),
        )
        content = resp["choices"][0]["message"]["content"]
        return {
            "id": resp.get("id", "msg_aegis"),
            "type": "message",
            "role": "assistant",
            "model": resp.get("model", model),
            "content": [{"type": "text", "text": content}],
            "stop_reason": "end_turn",
            "usage": resp.get("usage", {}),
            "aegis": resp.get("aegis", {}),
        }

    @staticmethod
    def _to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for msg in messages:
            role = str(msg.get("role", "user"))
            content = msg.get("content")
            if isinstance(content, list):
                text_parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                text = "\n".join(text_parts)
            else:
                text = str(content or "")
            if role == "assistant":
                out.append({"role": "assistant", "content": text})
            else:
                out.append({"role": "user", "content": text})
        return out
