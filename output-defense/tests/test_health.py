from fastapi.testclient import TestClient

from aegis_output_defense.app import app


def test_health() -> None:
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "output-defense"
