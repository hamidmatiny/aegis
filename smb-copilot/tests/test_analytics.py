"""First-party pageview analytics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis_smb_copilot.main import app


def test_collect_and_summary(monkeypatch):
    monkeypatch.setenv("CORP_READONLY_TOKEN", "test-corp-ro")
    # Reload settings used by router — settings is already imported; patch object
    from aegis_smb_copilot import config
    from aegis_smb_copilot.analytics import router as analytics_router

    monkeypatch.setattr(config.settings, "corp_readonly_token", "test-corp-ro")
    monkeypatch.setattr(analytics_router.settings, "corp_readonly_token", "test-corp-ro")
    monkeypatch.setattr(analytics_router.settings, "internal_token", "")

    client = TestClient(app)
    r = client.post(
        "/analytics/collect",
        json={
            "path": "/guides/smb-cve-exposure-checklist",
            "referrer": "https://example.com/",
            "title": "test",
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    denied = client.get("/analytics/summary?days=7&path_prefix=/guides/")
    assert denied.status_code == 401

    ok = client.get(
        "/analytics/summary?days=7&path_prefix=/guides/",
        headers={"Authorization": "Bearer test-corp-ro"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["total_views"] >= 1
    assert any(p["path"] == "/guides/smb-cve-exposure-checklist" for p in body["by_path"])
