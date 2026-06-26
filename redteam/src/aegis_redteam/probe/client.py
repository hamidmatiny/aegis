"""HTTP clients for defense services."""

from __future__ import annotations

from typing import Any

import httpx

from aegis_redteam.models import DefenseTarget


class DefenseClient:
    def __init__(
        self,
        input_url: str,
        output_url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._input_url = input_url.rstrip("/")
        self._output_url = output_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def probe(
        self,
        target: DefenseTarget,
        payload: str,
        *,
        enabled_detectors: list[str] | None = None,
    ) -> dict[str, Any]:
        if target == DefenseTarget.INPUT_DEFENSE:
            url = f"{self._input_url}/analyze"
            body: dict[str, Any] = {"text": payload}
        else:
            url = f"{self._output_url}/analyze"
            body = {"content": payload}
        if enabled_detectors is not None:
            body["enabled_detectors"] = enabled_detectors

        resp = await self._client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
        verdict = data.get("verdict", data)
        return {
            "action": str(verdict.get("action", "ALLOW")),
            "fused_score": float(verdict.get("fused_score", 0.0)),
        }
