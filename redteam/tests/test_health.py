"""Health endpoint tests."""

from fastapi.testclient import TestClient

from aegis_redteam.app import app


def test_health() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "redteam"
        assert data["stage"] == "7"


def test_ready() -> None:
    with TestClient(app) as client:
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


def test_list_strategies() -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/strategies")
        assert resp.status_code == 200
        strategies = resp.json()["strategies"]
        assert len(strategies) >= 5
        assert any(s["strategy_id"] == "identity" for s in strategies)


def test_list_campaigns_empty() -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/campaigns")
        assert resp.status_code == 200
        assert resp.json()["campaigns"] == []
