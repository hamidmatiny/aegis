"""HTTP clients the harness loop uses to talk to model-router and
agent-gate.

`ModelClient` and `GateClient` are the two `Protocol`s loop.py actually
depends on -- the real classes below implement them, and so does anything
a test or a future alternative backend wants to substitute. This is the
same extensibility pattern as tool.py's `Tool`/`ToolRegistry`: the loop
never imports httpx or knows these are HTTP calls at all.

`aegis_sdk`'s existing `DefensePipeline.evaluate_tool` (sdk/python) was
considered and deliberately not reused here -- it raises on
AWAITING_HUMAN_APPROVAL/DENIED rather than returning a decision the
caller branches on, which doesn't fit the harness's need to poll a
pending approval to resolution. Kept these clients small and
self-contained instead of fighting that control-flow mismatch.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

# --- Protocols loop.py depends on -------------------------------------


class ModelClient(Protocol):
    async def complete(
        self, *, model: str, messages: list[dict[str, str]], provider: str = ""
    ) -> str:
        """Return the model's raw text response for the given message
        history. `provider` selects which upstream model-router should
        route to (e.g. "openai", "anthropic", "ollama", "vllm", "grok",
        "mock"); an empty string defers to model-router's own configured
        default, which is "mock" out of the box (see
        model-router/config/providers.yaml's routing.default_provider).
        Implementations decide how to reach a real model."""
        ...


class GateClient(Protocol):
    async def evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str,
        risk_level: str = "",
    ) -> GateDecision:
        """Submit a tool call for evaluation. Must not execute anything
        -- the caller (loop.py) executes only after inspecting the
        returned decision."""
        ...

    async def wait_for_approval(
        self, approval_request_id: str, *, timeout_seconds: float, poll_interval_seconds: float
    ) -> GateDecision:
        """Poll a pending approval until a reviewer decides it or the
        timeout elapses."""
        ...


@dataclass
class GateDecision:
    status: str
    denial_reason: str | None = None
    approval_request_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.status == "APPROVED"

    @property
    def awaiting_approval(self) -> bool:
        return self.status == "AWAITING_HUMAN_APPROVAL"


# --- Real HTTP implementations -----------------------------------------


class ModelRouterClient:
    """Talks to model-router's POST /v1/chat/completions.

    model-router enforces AEGIS_INTERNAL_TOKEN on every non-health route
    since Stage A.2 (model-router/internal/auth) -- sent here as
    `Authorization: Bearer <internal_token>`, the same convention every
    other internal-only AEGIS service uses.
    """

    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str = "",
        timeout: float = 60.0,
        trust_env: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_token = internal_token
        self.timeout = timeout
        # trust_env controls whether httpx honors HTTP_PROXY/NO_PROXY-style
        # env vars, same as httpx's own default -- exposed here (rather
        # than hardcoded) so a caller that genuinely needs a corporate
        # proxy to reach model-router keeps that working, while tests
        # that talk to a local mock server can turn it off explicitly.
        self.trust_env = trust_env

    async def complete(
        self, *, model: str, messages: list[dict[str, str]], provider: str = ""
    ) -> str:
        headers = {}
        if self.internal_token:
            headers["Authorization"] = f"Bearer {self.internal_token}"
        payload: dict[str, Any] = {"model": model, "messages": messages}
        # Omitted entirely (rather than sent as "") when unset, matching
        # model-router's own `json:"provider,omitempty"` -- and because
        # model-router's ResolveChain only falls back to its configured
        # default_provider ("mock") when the field is genuinely absent,
        # this is the one line that decides whether a run talks to a real
        # model or the mock echo. See harness/README.md's "Testing against
        # a real model" section for why this exists.
        if provider:
            payload["provider"] = provider
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=self.trust_env) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        content = data.get("content")
        if not isinstance(content, str):
            raise ValueError(f"model-router response missing string 'content': {data!r}")
        return content


class AgentGateClient:
    """Talks to agent-gate's POST /v1/evaluate and GET /v1/approvals/{id}.

    Uses the Service key only (never the Reviewer key) -- this client
    submits tool calls for evaluation, it never decides an approval
    itself. That split is deliberate and pre-existing (see
    agent-gate/internal/auth): a caller that could both submit and
    approve its own tool calls could approve its own irreversible
    actions, which is exactly the vulnerability this project's
    self-approval-prevention design already closed once, project-wide.
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_api_key: str,
        tenant_id: str = "default",
        timeout: float = 30.0,
        trust_env: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_api_key = service_api_key
        self.tenant_id = tenant_id
        self.timeout = timeout
        self.trust_env = trust_env

    async def evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str,
        risk_level: str = "",
    ) -> GateDecision:
        headers = (
            {"Authorization": f"Bearer {self.service_api_key}"} if self.service_api_key else {}
        )
        tool_call: dict[str, Any] = {
            "tool_name": tool_name,
            "agent_id": agent_id,
            "arguments": [
                {"name": name, "value": value} for name, value in arguments.items()
            ],
        }
        # Informational only -- policy-engine's tool_catalog is always
        # authoritative on conflict (it takes the higher of this and the
        # catalog-registered value), so declaring it here can never
        # weaken enforcement, only enrich the audit trail. See
        # policy-engine/policies/default.yaml's tool_catalog comment.
        if risk_level:
            tool_call["risk_level"] = risk_level
        payload = {
            "tenant_id": self.tenant_id,
            "mode": "enforce",
            "tool_call": tool_call,
        }
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=self.trust_env) as client:
            resp = await client.post(f"{self.base_url}/v1/evaluate", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return self._decision_from(data.get("decision", {}), data)

    async def wait_for_approval(
        self, approval_request_id: str, *, timeout_seconds: float, poll_interval_seconds: float
    ) -> GateDecision:
        headers = (
            {"Authorization": f"Bearer {self.service_api_key}"} if self.service_api_key else {}
        )
        deadline = time.monotonic() + timeout_seconds
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=self.trust_env) as client:
            while True:
                resp = await client.get(
                    f"{self.base_url}/v1/approvals/{approval_request_id}", headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "")
                if status in ("APPROVED", "DENIED"):
                    return self._decision_from(
                        {
                            "status": status,
                            "denial_reason": data.get("review_comment"),
                            "approval_request_id": approval_request_id,
                        },
                        data,
                    )
                if time.monotonic() >= deadline:
                    return GateDecision(
                        status="TIMED_OUT",
                        denial_reason="no reviewer decision within the wait timeout",
                        approval_request_id=approval_request_id,
                        raw=data,
                    )
                await asyncio.sleep(poll_interval_seconds)

    @staticmethod
    def _decision_from(decision: dict[str, Any], raw: dict[str, Any]) -> GateDecision:
        return GateDecision(
            status=decision.get("status", ""),
            denial_reason=decision.get("denial_reason"),
            approval_request_id=decision.get("approval_request_id"),
            raw=raw,
        )
