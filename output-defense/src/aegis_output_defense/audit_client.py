"""Emit signed audit receipts to the audit service."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aegis_output_defense.models import OutputVerdict, TraceContext

logger = logging.getLogger(__name__)


class AuditClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._enabled = bool(base_url)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def emit_output_verdict(
        self,
        *,
        tenant_id: str,
        trace: TraceContext | None,
        verdict: OutputVerdict,
        policy_pack_id: str = "",
        policy_pack_version: str = "",
    ) -> None:
        if not self._enabled:
            return
        payload: dict[str, Any] = {
            "event_type": "OUTPUT_DEFENSE",
            "tenant_id": tenant_id,
            "output_verdict": verdict.model_dump(mode="json"),
        }
        if trace is not None:
            payload["trace"] = trace.model_dump(exclude_none=True)
        if policy_pack_id:
            payload["policy_pack_id"] = policy_pack_id
        if policy_pack_version:
            payload["policy_pack_version"] = policy_pack_version
        await self._write(payload)

    async def _write(self, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(f"{self._base_url}/v1/receipts", json=payload)
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("audit emit failed: %s", exc)
