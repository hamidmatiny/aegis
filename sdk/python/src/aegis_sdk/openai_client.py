"""OpenAI-compatible client backed by the AEGIS defense pipeline."""

from __future__ import annotations

from typing import Any

import httpx

from aegis_sdk.errors import (
    AegisApprovalRequiredError,
    AegisPolicyBlockedError,
    AegisProviderError,
)
from aegis_sdk.pipeline import DefensePipeline
from aegis_sdk.settings import settings


def _run_sync(coro: Any) -> Any:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Use the async variant from an async context")


class _Completions:
    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return _run_sync(self._client._create_completion_async(**kwargs))


class _Chat:
    def __init__(self, client: OpenAI) -> None:
        self.completions = _Completions(client)


class _Tools:
    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def evaluate(self, *, tool_call: dict[str, Any], **kwargs: Any) -> Any:
        return _run_sync(self._client._evaluate_tool_async(tool_call=tool_call, **kwargs))


class OpenAI:
    """
    Drop-in style client for OpenAI chat completions through AEGIS.

    Reverse-proxy mode: set ``base_url="http://localhost:8080/v1"`` (or
    ``OPENAI_BASE_URL``) so existing OpenAI SDK apps need no code changes.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        tenant_id: str | None = None,
        timeout: float = 60.0,
        input_defense_url: str | None = None,
        output_defense_url: str | None = None,
        policy_engine_url: str | None = None,
        model_router_url: str | None = None,
        agent_gate_url: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.tenant_id = tenant_id or settings.default_tenant_id
        self.timeout = timeout
        self._pipeline: DefensePipeline | None = None
        if self.base_url is None:
            self._pipeline = DefensePipeline(
                input_defense_url=input_defense_url or settings.input_defense_url,
                output_defense_url=output_defense_url or settings.output_defense_url,
                policy_engine_url=policy_engine_url or settings.policy_engine_url,
                model_router_url=model_router_url or settings.model_router_url,
                agent_gate_url=agent_gate_url or settings.agent_gate_url,
                tenant_id=self.tenant_id,
                timeout=timeout,
            )
        self.chat = _Chat(self)
        self.tools = _Tools(self)

    async def _create_completion_async(self, **kwargs: Any) -> Any:
        if self.base_url:
            return await self._proxy_chat(**kwargs)
        if self._pipeline is None:
            raise RuntimeError("pipeline not configured")
        messages = kwargs.get("messages") or []
        model = kwargs.get("model") or settings.default_model
        return await self._pipeline.chat_completions(
            model=model,
            messages=messages,
            provider=kwargs.get("provider"),
            stream=bool(kwargs.get("stream")),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
        )

    async def _evaluate_tool_async(self, *, tool_call: dict[str, Any], **kwargs: Any) -> Any:
        del kwargs
        if self.base_url:
            raise AegisProviderError(
                "Tool evaluation requires embedded SDK mode (omit base_url)",
                error_type="unsupported_in_proxy_mode",
            )
        if self._pipeline is None:
            raise RuntimeError("pipeline not configured")
        return await self._pipeline.evaluate_tool(tool_call=tool_call)

    async def _proxy_chat(self, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=kwargs, headers=headers)
            body: dict[str, Any] = {}
            try:
                body = resp.json()
            except Exception:
                body = {"error": resp.text}
            if resp.status_code == 403:
                err = body.get("error") or {}
                if err.get("type") == "aegis_approval_required":
                    raise AegisApprovalRequiredError(
                        str(err.get("message", "approval required")),
                        approval_id=str(err.get("approval_id", "")),
                        tool_name=err.get("tool_name"),
                        details=body,
                    )
                raise AegisPolicyBlockedError(
                    str(err.get("message", "blocked by policy")),
                    layer=str(err.get("layer", "policy")),
                    policy_action=err.get("policy_action"),
                    details=body,
                )
            if resp.status_code >= 400:
                err = body.get("error")
                if isinstance(err, dict):
                    msg = str(err.get("message", err))
                    error_type = err.get("type")
                else:
                    msg = str(err or body)
                    error_type = None
                raise AegisProviderError(
                    msg,
                    status_code=resp.status_code,
                    error_type=str(error_type) if error_type else "provider_error",
                    details=body if isinstance(body, dict) else {"error": body},
                )
            return body
