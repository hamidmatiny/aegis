"""Proxy endpoint tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from aegis_sdk.proxy.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "aegis-sdk-proxy"
    assert data["stage"] == "10"


@respx.mock
def test_proxy_blocks_attack(client: TestClient) -> None:
    respx.post("http://localhost:8090/analyze").mock(
        return_value=httpx.Response(
            200,
            json={
                "verdict": {
                    "action": "BLOCK",
                    "fused_score": 0.99,
                    "detector_scores": [],
                    "total_latency_ms": 1,
                }
            },
        )
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-model", "messages": [{"role": "user", "content": "attack"}]},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["type"] == "aegis_policy_blocked"
