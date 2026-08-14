"""Internal service token enforcement (Stage A.1)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis_input_defense.internal_auth import InternalTokenMiddleware


def _app(token: str) -> TestClient:
    app = FastAPI()
    app.add_middleware(InternalTokenMiddleware, token=token)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        return {"status": "ready"}

    @app.post("/analyze")
    async def analyze():
        return {"ok": True}

    return TestClient(app)


def test_rejects_missing_token():
    client = _app("secret-token")
    resp = client.post("/analyze")
    assert resp.status_code == 401


def test_rejects_wrong_token():
    client = _app("secret-token")
    resp = client.post("/analyze", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_accepts_bearer_token():
    client = _app("secret-token")
    resp = client.post("/analyze", headers={"Authorization": "Bearer secret-token"})
    assert resp.status_code == 200


def test_accepts_alternate_header():
    client = _app("secret-token")
    resp = client.post("/analyze", headers={"X-Aegis-Internal-Token": "secret-token"})
    assert resp.status_code == 200


def test_exempts_health_and_ready():
    client = _app("secret-token")
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
