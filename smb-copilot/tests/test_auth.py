"""Auth integration tests (Postgres + Redis required)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from aegis_smb_copilot.auth.passwords import hash_password


def _host_database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or urlparse(raw).hostname == "postgres":
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.is_file():
            for line in env_path.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not raw:
        raw = "postgres://aegis:aegis_dev@127.0.0.1:5432/aegis?sslmode=disable"
    parsed = urlparse(raw)
    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo += f":{parsed.password}"
        userinfo += "@"
    port = parsed.port or 5432
    netloc = f"{userinfo}127.0.0.1:{port}"
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


def _host_redis_url() -> str:
    pwd = "aegis_redis_dev"
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            if line.startswith("REDIS_PASSWORD="):
                pwd = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
            if line.startswith("REDIS_URL="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                parsed = urlparse(raw)
                if parsed.password:
                    pwd = parsed.password
    return f"redis://:{pwd}@127.0.0.1:6379/0"


os.environ["DATABASE_URL"] = _host_database_url()
os.environ["REDIS_URL"] = _host_redis_url()
os.environ.setdefault(
    "AEGIS_POLICY_TENANTS_DIR",
    str(Path(__file__).resolve().parents[2] / ".pytest_policy_tenants"),
)
os.environ["SMB_SESSION_SECRET"] = "test-session-secret-for-pytest-only"
os.environ["SMB_COOKIE_SECURE"] = "false"
os.environ["ADMIN_USERNAME"] = "test-admin"
os.environ["ADMIN_PASSWORD_HASH"] = hash_password("test-admin-password")

import pytest
from fastapi.testclient import TestClient

from aegis_smb_copilot import config as config_mod
from aegis_smb_copilot.auth import sessions as sessions_mod
from aegis_smb_copilot.db import connection as db_connection
from aegis_smb_copilot.qa import rate_limit as rate_limit_mod

Path(os.environ["AEGIS_POLICY_TENANTS_DIR"]).mkdir(parents=True, exist_ok=True)
config_mod.settings = config_mod.Settings()
sessions_mod.reset_redis_for_tests()
rate_limit_mod.reset_redis_for_tests()

from aegis_smb_copilot.main import app  # noqa: E402


def _postgres_ready() -> bool:
    try:
        db_connection.close_pool()
        pool = db_connection.ConnectionPool(
            conninfo=os.environ["DATABASE_URL"],
            kwargs={"autocommit": True, "connect_timeout": 3},
            configure=db_connection._configure,
            open=True,
            min_size=1,
            max_size=2,
            timeout=5,
        )
        try:
            with pool.connection() as conn:
                conn.execute("SELECT 1")
                conn.execute("SELECT 1 FROM customers LIMIT 0")
        finally:
            pool.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_ready(),
    reason="Postgres with SMB customers schema not available",
)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    db_connection.close_pool()
    sessions_mod.reset_redis_for_tests()
    rate_limit_mod.reset_redis_for_tests()
    config_mod.settings = config_mod.Settings()
    with TestClient(app) as test_client:
        yield test_client
    db_connection.close_pool()


def _register(client: TestClient, email: str | None = None) -> dict:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    slug = f"auth-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure-pass-123", "slug": slug},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_register_login_logout_me(client: TestClient) -> None:
    email = f"flow-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/auth/register",
        json={"email": email, "password": "secure-pass-123", "slug": f"flow-{uuid.uuid4().hex[:6]}"},
    )
    assert reg.status_code == 201
    assert "api_key" in reg.json()
    assert "password" not in reg.json()

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "customer"
    assert me.json()["email"] == email

    client.post("/auth/logout")
    me_guest = client.get("/auth/me")
    assert me_guest.json()["role"] == "guest"

    login = client.post("/auth/login", json={"email": email, "password": "secure-pass-123"})
    assert login.status_code == 200
    me2 = client.get("/auth/me")
    assert me2.json()["role"] == "customer"


def test_wrong_password_rejected(client: TestClient) -> None:
    email = f"bad-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": "secure-pass-123", "slug": f"bad-{uuid.uuid4().hex[:6]}"},
    )
    client.post("/auth/logout")
    bad = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert bad.status_code == 401


def test_admin_login_separate_from_customer(client: TestClient) -> None:
    admin = client.post(
        "/auth/admin-login",
        json={"username": "test-admin", "password": "test-admin-password"},
    )
    assert admin.status_code == 200
    me = client.get("/auth/me")
    assert me.json()["role"] == "admin"

    customer_login = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "nope"},
    )
    assert customer_login.status_code == 401


def test_customer_session_forbidden_on_admin_routes(client: TestClient) -> None:
    _register(client)
    resp = client.get("/admin/tenants")
    assert resp.status_code == 403


def test_admin_session_forbidden_on_admin_routes_for_customer_api(client: TestClient) -> None:
    email = f"adm-{uuid.uuid4().hex[:8]}@example.com"
    slug = f"adm-{uuid.uuid4().hex[:6]}"
    reg = client.post(
        "/auth/register",
        json={"email": email, "password": "secure-pass-123", "slug": slug},
    )
    assert reg.status_code == 201
    client.post("/auth/logout")
    client.post(
        "/auth/admin-login",
        json={"username": "test-admin", "password": "test-admin-password"},
    )
    resp = client.get("/billing/usage")
    assert resp.status_code == 403

    client.post("/auth/logout")
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "secure-pass-123"},
    )
    assert login.status_code == 200


def test_admin_can_list_tenants(client: TestClient) -> None:
    _register(client)
    client.post("/auth/logout")
    client.post(
        "/auth/admin-login",
        json={"username": "test-admin", "password": "test-admin-password"},
    )
    resp = client.get("/admin/tenants")
    assert resp.status_code == 200
    assert len(resp.json()["tenants"]) >= 1


def test_upsell_response_has_no_internal_paths(client: TestClient) -> None:
    from unittest.mock import patch

    from aegis_smb_copilot.billing.tier_gate import TierDecision

    reg = _register(client)
    api_key = reg["api_key"]
    denied = TierDecision(
        allowed=False,
        action="block",
        tenant_slug=reg["slug"],
        block_reason="smb-deny-walkthrough",
    )
    with patch(
        "aegis_smb_copilot.qa.router.check_walkthrough_allowed",
        return_value=denied,
    ):
        resp = client.post(
            "/qa/ask",
            json={"question": "Walk me through hardening", "walkthrough": True},
        )
    assert resp.status_code == 200
    body = resp.text
    assert "overrides.yaml" not in body
    assert "/v1/reload" not in body
    assert "policy-engine/policies" not in body

    client.post("/auth/logout")
    with patch(
        "aegis_smb_copilot.qa.router.check_walkthrough_allowed",
        return_value=denied,
    ):
        resp2 = client.post(
            "/qa/ask",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"question": "Walk me through hardening", "walkthrough": True},
        )
    assert "overrides.yaml" not in resp2.text
