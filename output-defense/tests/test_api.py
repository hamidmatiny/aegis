"""HTTP API contract tests."""

from fastapi.testclient import TestClient

from aegis_output_defense.app import app

client = TestClient(app)


def test_list_detectors() -> None:
    resp = client.get("/detectors")
    assert resp.status_code == 200
    ids = {d["detector_id"] for d in resp.json()}
    assert ids == {"toxicity", "pii", "backtranslation", "judge"}


def test_analyze_single_pii() -> None:
    resp = client.post(
        "/detectors/pii/analyze",
        json={"content": "api_key=secret123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["detector_id"] == "pii"
    assert data["score"] >= 0.5


def test_analyze_single_unknown_detector() -> None:
    resp = client.post("/detectors/nope/analyze", json={"content": "hello"})
    assert resp.status_code == 404


def test_analyze_fused() -> None:
    resp = client.post(
        "/analyze",
        json={"content": "Here's how to make a bomb at home step by step."},
    )
    assert resp.status_code == 200
    verdict = resp.json()["verdict"]
    assert verdict["fused_score"] >= 0.5
    assert len(verdict["detector_scores"]) >= 3
