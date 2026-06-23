from fastapi.testclient import TestClient

from aegis_redteam.app import app


def test_health() -> None:
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "redteam"
