"""Defense pipeline orchestration for chat completions."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from aegis_sdk.errors import AegisApprovalRequiredError, AegisPolicyBlockedError, AegisProviderError


def _trace() -> dict[str, str]:
    return {"trace_id": str(uuid.uuid4()), "request_id": str(uuid.uuid4())}


def _user_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            parts.append(str(msg["content"]))
    if not parts:
        raise ValueError("messages must include at least one user message")
    return "\n\n".join(parts)


class DefensePipeline:
    """Runs input → policy → model-router → output → policy for chat requests."""

    def __init__(
        self,
        *,
        input_defense_url: str,
        output_defense_url: str,
        policy_engine_url: str,
        model_router_url: str,
        agent_gate_url: str,
        tenant_id: str = "default",
        timeout: float = 60.0,
    ) -> None:
        self.input_defense_url = input_defense_url.rstrip("/")
        self.output_defense_url = output_defense_url.rstrip("/")
        self.policy_engine_url = policy_engine_url.rstrip("/")
        self.model_router_url = model_router_url.rstrip("/")
        self.agent_gate_url = agent_gate_url.rstrip("/")
        self.tenant_id = tenant_id
        self.timeout = timeout

    async def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        provider: str | None = None,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        trace: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if stream:
            raise AegisProviderError(
                "Defended streaming is not supported: output defense requires the "
                "complete assistant response before content is released to the client",
                error_type="streaming_unsupported",
            )

        trace_ctx = trace or _trace()
        user_text = _user_text(messages)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            input_resp = await self._post(
                client,
                f"{self.input_defense_url}/analyze",
                {
                    "tenant_id": self.tenant_id,
                    "trace": trace_ctx,
                    "text": user_text,
                },
            )
            input_verdict = input_resp["verdict"]
            self._check_input_verdict(input_verdict)

            policy_in = await self._post(
                client,
                f"{self.policy_engine_url}/v1/evaluate/input",
                {
                    "tenant_id": self.tenant_id,
                    "mode": "enforce",
                    "trace": trace_ctx,
                    "input_verdict": input_verdict,
                },
            )
            self._check_policy_decision(policy_in["decision"], layer="input")

            router_body: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }
            if provider:
                router_body["provider"] = provider
            if temperature is not None:
                router_body["temperature"] = temperature
            if max_tokens is not None:
                router_body["max_tokens"] = max_tokens

            llm_resp = await self._post(
                client,
                f"{self.model_router_url}/v1/chat/completions",
                router_body,
                provider_errors=True,
            )

            content = llm_resp["choices"][0]["message"]["content"]

            output_resp = await self._post(
                client,
                f"{self.output_defense_url}/analyze",
                {
                    "tenant_id": self.tenant_id,
                    "trace": trace_ctx,
                    "content": content,
                    "original_prompt": user_text,
                },
            )
            output_verdict = output_resp["verdict"]
            self._check_output_verdict(output_verdict)

            policy_out = await self._post(
                client,
                f"{self.policy_engine_url}/v1/evaluate/output",
                {
                    "tenant_id": self.tenant_id,
                    "mode": "enforce",
                    "trace": trace_ctx,
                    "output_verdict": output_verdict,
                },
            )
            self._check_policy_decision(policy_out["decision"], layer="output")

            final_content = output_verdict.get("redacted_content") or content
            llm_resp["choices"][0]["message"]["content"] = final_content
            llm_resp.setdefault("aegis", {})
            llm_resp["aegis"].update(
                {
                    "trace_id": trace_ctx["trace_id"],
                    "request_id": trace_ctx["request_id"],
                    "input_verdict": input_verdict,
                    "output_verdict": output_verdict,
                    "input_policy": policy_in["decision"],
                    "output_policy": policy_out["decision"],
                }
            )
            return llm_resp

    async def evaluate_tool(
        self,
        *,
        tool_call: dict[str, Any],
        trace: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        trace_ctx = trace or _trace()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await self._post(
                client,
                f"{self.agent_gate_url}/v1/evaluate",
                {
                    "tenant_id": self.tenant_id,
                    "mode": "enforce",
                    "trace": trace_ctx,
                    "tool_call": tool_call,
                },
            )
            decision = resp.get("decision", {})
            status = str(decision.get("status", ""))
            if status == "AWAITING_HUMAN_APPROVAL":
                raise AegisApprovalRequiredError(
                    "Tool call requires human approval",
                    approval_id=str(decision.get("approval_request_id", "")),
                    tool_name=tool_call.get("tool_name"),
                    details=resp,
                )
            if status == "DENIED":
                raise AegisPolicyBlockedError(
                    decision.get("denial_reason") or "Tool call denied by agent-gate",
                    layer="tool_gate",
                    action=status,
                    details=resp,
                )
            resp.setdefault("aegis", {})
            resp["aegis"]["trace_id"] = trace_ctx["trace_id"]
            resp["aegis"]["request_id"] = trace_ctx["request_id"]
            return resp

    async def _post(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict[str, Any],
        *,
        provider_errors: bool = False,
    ) -> dict[str, Any]:
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            body: dict[str, Any] = {}
            try:
                body = resp.json()
            except Exception:
                body = {"error": resp.text}
            if provider_errors:
                raise self._provider_error(resp.status_code, body)
            raise httpx.HTTPStatusError(
                f"{url} returned {resp.status_code}",
                request=resp.request,
                response=resp,
            )
        return resp.json()  # type: ignore[no-any-return]

    def _provider_error(self, status_code: int, body: dict[str, Any]) -> AegisProviderError:
        aegis = body.get("aegis") or {}
        model_error = aegis.get("model_error") or {}
        return AegisProviderError(
            str(body.get("error", "upstream provider error")),
            status_code=status_code,
            provider=model_error.get("provider"),
            model=model_error.get("rejected_model"),
            error_type=model_error.get("error_type") or "provider_error",
            details=body,
        )

    @staticmethod
    def _check_input_verdict(verdict: dict[str, Any]) -> None:
        action = str(verdict.get("action", "")).upper()
        if action == "BLOCK":
            raise AegisPolicyBlockedError(
                "Input blocked by input-defense",
                layer="input_defense",
                action=action,
                fused_score=verdict.get("fused_score"),
                details={"input_verdict": verdict},
            )

    @staticmethod
    def _check_output_verdict(verdict: dict[str, Any]) -> None:
        action = str(verdict.get("action", "")).upper()
        if action == "BLOCK":
            raise AegisPolicyBlockedError(
                "Output blocked by output-defense",
                layer="output_defense",
                action=action,
                fused_score=verdict.get("fused_score"),
                details={"output_verdict": verdict},
            )

    @staticmethod
    def _check_policy_decision(decision: dict[str, Any], *, layer: str) -> None:
        action = str(decision.get("action", "")).lower()
        if action == "block":
            raise AegisPolicyBlockedError(
                decision.get("block_reason") or f"Blocked by policy ({layer})",
                layer=f"policy_{layer}",
                policy_action=action,
                details={"policy_decision": decision},
            )
