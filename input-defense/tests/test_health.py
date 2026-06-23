"""Health endpoint tests."""

from fastapi.testclient import TestClient

from aegis_input_defense.app import app


def test_health() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "input-defense"
