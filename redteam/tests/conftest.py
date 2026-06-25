"""Shared pytest fixtures."""

from __future__ import annotations

import httpx
import pytest

from aegis_redteam.metrics import load_fixtures
from aegis_redteam.models import AttackFixture
from aegis_redteam.probe.client import DefenseClient
from aegis_redteam.service import RedTeamService


@pytest.fixture(scope="session")
def all_fixtures() -> list[AttackFixture]:
    return load_fixtures()


@pytest.fixture(scope="session")
def attack_fixtures(all_fixtures: list[AttackFixture]) -> list[AttackFixture]:
    return [f for f in all_fixtures if f.is_attack]


def _mock_defense_response(payload: str) -> dict:
    lower = payload.lower()
    blocked_markers = (
        "ignore all previous",
        "dan",
        "developer mode",
        "api key",
        "sk-live",
        "bomb",
        "malware",
        "private key",
        "jailbreak successful",
        "unrestricted ai",
    )
    if any(marker in lower for marker in blocked_markers):
        return {"verdict": {"action": "BLOCK", "fused_score": 0.92}}
    if "hypothetically" in lower:
        return {"verdict": {"action": "ESCALATE", "fused_score": 0.62}}
    return {"verdict": {"action": "ALLOW", "fused_score": 0.12}}


@pytest.fixture
async def mock_service() -> RedTeamService:
    import json

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        payload = body.get("text") or body.get("content") or ""
        return httpx.Response(200, json=_mock_defense_response(payload))

    transport = httpx.MockTransport(handler)
    client = DefenseClient(
        "http://input-defense",
        "http://output-defense",
        client=httpx.AsyncClient(transport=transport),
    )
    service = RedTeamService(client, threshold=0.50, store_bypasses=True)
    yield service
    await client.close()
