"""Health endpoint tests."""

from fastapi.testclient import TestClient

from aegis_output_defense.app import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "output-defense"
    assert data["stage"] == "5"


def test_ready() -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
