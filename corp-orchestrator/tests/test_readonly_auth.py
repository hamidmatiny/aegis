"""Auth boundary: CORP_READONLY_TOKEN is GET-only; admin/internal stay full-access."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

# Env must be set before Settings() is constructed in fixtures.
_INTERNAL = "test-internal-token-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_READONLY = "test-readonly-token-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_SECRET = "test-smb-session-secret-for-corp-auth-pytest"

os.environ["AEGIS_INTERNAL_TOKEN"] = _INTERNAL
os.environ["CORP_READONLY_TOKEN"] = _READONLY
os.environ["SMB_SESSION_SECRET"] = _SECRET
os.environ["CORP_SCHEDULER_ENABLED"] = "false"
os.environ["CORP_FORCE_MOCK_LLM"] = "true"

from aegis_corp_orchestrator import config as config_mod  # noqa: E402
from aegis_corp_orchestrator.auth import session as session_mod  # noqa: E402
from aegis_smb_session.sessions import SessionData  # noqa: E402

config_mod.settings = config_mod.Settings()
session_mod.settings = config_mod.settings

from aegis_corp_orchestrator.routers import agents as agents_mod  # noqa: E402
from aegis_corp_orchestrator.routers import bev as bev_mod  # noqa: E402

GET_ROUTES = [
    "/v1/agents",
    "/v1/tasks",
    "/v1/tasks/pending",
    "/v1/bev/summary",
    "/v1/bev/departments/engineering",
    "/v1/bev/trajectory",
]

POST_ROUTES: list[tuple[str, dict[str, Any] | None]] = [
    ("/v1/tasks/run", {"department": "engineering", "team": "core_infra"}),
    (f"/v1/tasks/{uuid4()}/run", None),
    (f"/v1/tasks/{uuid4()}/decide", {"approved": False, "comment": "no"}),
    (
        "/v1/tasks/park-pending",
        {
            "department": "engineering",
            "team": "core_infra",
            "tool_name": "corp_escalate",
            "arguments": {},
        },
    ),
    ("/v1/tasks/run-all-departments", None),
    ("/v1/tasks/run-all-agents", None),
]


class _FakeConn:
    """Minimal connection stub so GET handlers return 200 without Postgres."""

    def execute(self, sql: str, params: Any = None) -> Any:
        cur = MagicMock()
        sql_l = " ".join(sql.lower().split())
        if "from agents where department = %s order by team" in sql_l:
            cur.fetchall.return_value = [
                (uuid4(), "core_infra", "role", "idle", "mock", "mock-model", "0 * * * *"),
            ]
        elif "from agents where department = %s and team = %s" in sql_l:
            cur.fetchone.return_value = (uuid4(),)
        elif "select department, team from agents where agent_id" in sql_l:
            cur.fetchone.return_value = ("engineering", "core_infra")
        elif "department = 'executive' and team = 'ceo'" in sql_l:
            cur.fetchone.return_value = (
                uuid4(),
                "idle",
                "grok",
                "grok-4",
                "0 7 * * *",
                {"allowed_tools": []},
            )
        elif "select count(*) from agents" in sql_l and "group by" not in sql_l:
            cur.fetchone.return_value = (13,)
        elif "group by status" in sql_l:
            cur.fetchall.return_value = [("idle", 13)]
        elif "group by department" in sql_l:
            cur.fetchall.return_value = [("engineering", 1)]
        elif "from tasks" in sql_l and "order by created_at desc limit 1" in sql_l:
            cur.fetchone.return_value = None
        elif "from tasks" in sql_l and "pending_approval" in sql_l:
            cur.fetchall.return_value = []
        elif "from tasks" in sql_l:
            cur.fetchall.return_value = []
            cur.fetchone.return_value = (0,)
        elif "from tenants" in sql_l:
            cur.fetchall.return_value = []
        elif "from agents order by" in sql_l:
            cur.fetchall.return_value = []
        else:
            cur.fetchall.return_value = []
            cur.fetchone.return_value = (0,)
        return cur


class _FakePool:
    @contextmanager
    def connection(self):
        yield _FakeConn()


_DEFAULT_MRR_SNAPSHOT: dict[str, Any] = {
    "source": "shared:aegis_corp_orchestrator.finance.mrr.get_mrr_snapshot",
    "unavailable": False,
    "paying_subscribers": 1,
    "unit_amount_cents": 2900,
    "monthly_unit_cents": 2900,
    "mrr_cents": 2900,
    "mrr_usd": 29.0,
    "currency": "CAD",
    "mrr_display": "$29.00 CAD",
    "price": {"ok": True, "unit_amount": 2900, "currency": "CAD", "interval": "month"},
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    pool = _FakePool()
    monkeypatch.setattr(agents_mod, "get_pool", lambda: pool)
    monkeypatch.setattr(bev_mod, "get_pool", lambda: pool)
    # Avoid live Stripe / DB from GET /bev/summary's mrr_snapshot field.
    monkeypatch.setattr(bev_mod, "get_mrr_snapshot", lambda: dict(_DEFAULT_MRR_SNAPSHOT))

    def fake_admin_session(request: Request) -> SessionData:
        cookie = request.cookies.get("aegis_smb_session")
        if cookie == "valid-admin-cookie":
            return SessionData(role="admin", username="cookie-admin")
        if cookie == "customer-cookie":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"type": "wrong_role", "message": "admin session required"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "not_authenticated", "message": "admin login required"},
        )

    monkeypatch.setattr(session_mod, "require_admin_session", fake_admin_session)

    app = FastAPI()
    app.include_router(agents_mod.router)
    app.include_router(bev_mod.router)
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_readonly_token_succeeds_on_all_get_routes(client: TestClient) -> None:
    for path in GET_ROUTES:
        resp = client.get(path, headers=_auth(_READONLY))
        assert resp.status_code == 200, f"{path} -> {resp.status_code} {resp.text}"


def test_readonly_token_rejected_on_all_post_routes(client: TestClient) -> None:
    for path, body in POST_ROUTES:
        if body is None:
            resp = client.post(path, headers=_auth(_READONLY))
        else:
            resp = client.post(path, headers=_auth(_READONLY), json=body)
        assert resp.status_code in (401, 403), (
            f"{path} must reject readonly token, got {resp.status_code}: {resp.text}"
        )


def test_internal_token_still_works_on_gets_and_posts(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    for path in GET_ROUTES:
        resp = client.get(path, headers=_auth(_INTERNAL))
        assert resp.status_code == 200, f"GET {path} internal -> {resp.status_code}"

    # POST /tasks/run: mock enqueue so we don't need agent-gate / harness.
    async def fake_enqueue(agent_id: Any, prompt: str) -> dict[str, Any]:
        return {
            "task_id": str(uuid4()),
            "agent_id": str(agent_id),
            "status": "done",
            "provider": "mock",
        }

    monkeypatch.setattr(agents_mod, "enqueue_and_run", fake_enqueue)
    resp = client.post(
        "/v1/tasks/run",
        headers=_auth(_INTERNAL),
        json={"department": "engineering", "team": "core_infra"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "done"


def test_admin_cookie_still_works_on_get_and_post(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.cookies.set("aegis_smb_session", "valid-admin-cookie")
    for path in GET_ROUTES:
        resp = client.get(path)
        assert resp.status_code == 200, f"cookie GET {path} -> {resp.status_code}"

    async def fake_enqueue(agent_id: Any, prompt: str) -> dict[str, Any]:
        return {"task_id": str(uuid4()), "agent_id": str(agent_id), "status": "done"}

    monkeypatch.setattr(agents_mod, "enqueue_and_run", fake_enqueue)
    resp = client.post(
        "/v1/tasks/run",
        json={"department": "engineering", "team": "core_infra"},
    )
    assert resp.status_code == 200, resp.text


def test_empty_readonly_token_does_not_open_gets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty CORP_READONLY_TOKEN must not match any bearer (including empty)."""
    monkeypatch.setattr(config_mod.settings, "readonly_token", "")
    monkeypatch.setattr(session_mod.settings, "readonly_token", "")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/v1/agents",
        "raw_path": b"/v1/agents",
        "query_string": b"",
        "headers": [(b"authorization", b"Bearer ")],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    request = StarletteRequest(scope)
    with pytest.raises(HTTPException) as exc:
        session_mod.require_read_or_admin(request)
    assert exc.value.status_code in (401, 403)


def test_bev_summary_includes_mrr_snapshot_from_shared_helper(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/bev/summary exposes get_mrr_snapshot() — numbers match the mocked Stripe path."""
    snap = {
        **_DEFAULT_MRR_SNAPSHOT,
        "paying_subscribers": 1,
        "mrr_cents": 2900,
        "mrr_usd": 29.0,
        "currency": "CAD",
        "mrr_display": "$29.00 CAD",
    }
    monkeypatch.setattr(bev_mod, "get_mrr_snapshot", lambda: snap)

    resp = client.get("/v1/bev/summary", headers=_auth(_READONLY))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "mrr_snapshot" in body
    assert body["mrr_snapshot"]["mrr_usd"] == 29.0
    assert body["mrr_snapshot"]["mrr_cents"] == 2900
    assert body["mrr_snapshot"]["currency"] == "CAD"
    assert body["mrr_snapshot"]["paying_subscribers"] == 1
    assert body["mrr_snapshot"]["unavailable"] is False
    assert "mrr_error" not in body


def test_bev_summary_mrr_exception_returns_null_not_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> dict[str, Any]:
        raise RuntimeError("stripe unreachable")

    monkeypatch.setattr(bev_mod, "get_mrr_snapshot", boom)
    resp = client.get("/v1/bev/summary", headers=_auth(_READONLY))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mrr_snapshot"] is None
    assert body["mrr_error"] == "stripe unreachable"
    assert body["total_agents"] == 13
