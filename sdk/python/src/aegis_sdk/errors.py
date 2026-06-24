"""Typed errors for AEGIS SDK consumers."""

from __future__ import annotations

from typing import Any


class AegisError(Exception):
    """Base error for all AEGIS SDK failures."""


class AegisPolicyBlockedError(AegisError):
    """Request blocked by input/output defense or policy engine."""

    def __init__(
        self,
        message: str,
        *,
        layer: str,
        action: str | None = None,
        fused_score: float | None = None,
        policy_action: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.layer = layer
        self.action = action
        self.fused_score = fused_score
        self.policy_action = policy_action
        self.details = details or {}


class AegisProviderError(AegisError):
    """Upstream LLM provider or model-router failure."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider: str | None = None,
        model: str | None = None,
        error_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider
        self.model = model
        self.error_type = error_type
        self.details = details or {}


class AegisApprovalRequiredError(AegisError):
    """Tool/MCP action requires human approval via agent-gate."""

    def __init__(
        self,
        message: str,
        *,
        approval_id: str,
        tool_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.approval_id = approval_id
        self.tool_name = tool_name
        self.details = details or {}
