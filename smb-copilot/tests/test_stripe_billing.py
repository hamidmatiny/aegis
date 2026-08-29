"""Stripe billing integration tests."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse, urlunparse


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
    return f"redis://:{pwd}@127.0.0.1:6379/0"


os.environ["DATABASE_URL"] = _host_database_url()
os.environ["REDIS_URL"] = _host_redis_url()
os.environ.setdefault(
    "AEGIS_POLICY_TENANTS_DIR",
    str(Path(__file__).resolve().parents[2] / ".pytest_policy_tenants"),
)
os.environ["SMB_SESSION_SECRET"] = "test-session-secret-for-pytest-only"
os.environ["SMB_COOKIE_SECURE"] = "false"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_fake"
os.environ["STRIPE_PRICE_ID_STANDARD"] = "price_test_standard"
os.environ["SMB_PORTAL_BASE_URL"] = "http://127.0.0.1:3001"

import pytest
from fastapi.testclient import TestClient

from aegis_smb_copilot import config as config_mod
from aegis_smb_copilot.auth import sessions as sessions_mod
from aegis_smb_copilot.auth.passwords import hash_password
from aegis_smb_copilot.db import connection as db_connection
from aegis_smb_copilot.qa import rate_limit as rate_limit_mod

Path(os.environ["AEGIS_POLICY_TENANTS_DIR"]).mkdir(parents=True, exist_ok=True)
config_mod.settings = config_mod.Settings()
sessions_mod.reset_redis_for_tests()
rate_limit_mod.reset_redis_for_tests()

os.environ["ADMIN_USERNAME"] = "test-admin"
os.environ["ADMIN_PASSWORD_HASH"] = hash_password("test-admin-password")
config_mod.settings = config_mod.Settings()

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
                conn.execute("SELECT stripe_customer_id FROM customers LIMIT 0")
        finally:
            pool.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_ready(),
    reason="Postgres with SMB stripe schema not available",
)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    db_connection.close_pool()
    sessions_mod.reset_redis_for_tests()
    config_mod.settings = config_mod.Settings()
    with TestClient(app) as test_client:
        yield test_client
    db_connection.close_pool()


def _register_customer(client: TestClient) -> dict:
    email = f"bill-{uuid.uuid4().hex[:8]}@example.com"
    slug = f"bill-{uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure-pass-123", "slug": slug},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _checkout_event(tenant_id: str) -> dict:
    return {
        "metadata": {"tenant_id": tenant_id},
        "customer": "cus_test_123",
        "subscription": "sub_test_456",
    }


def test_webhook_rejects_invalid_signature(client: TestClient) -> None:
    with patch(
        "aegis_smb_copilot.billing.stripe_service.stripe.Webhook.construct_event",
        side_effect=__import__("stripe").error.SignatureVerificationError(
            "bad sig", "sig_header"
        ),
    ):
        resp = client.post(
            "/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "bad"},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"]["type"] == "invalid_signature"


def test_webhook_rejects_missing_signature(client: TestClient) -> None:
    resp = client.post("/billing/webhook", data=b"{}")
    assert resp.status_code == 400
    assert resp.json()["detail"]["type"] == "missing_signature"


@patch("aegis_smb_copilot.billing.stripe_service.set_tenant_tier")
def test_webhook_checkout_completed_flips_tier_once(
    mock_set_tier: MagicMock,
    client: TestClient,
) -> None:
    reg = _register_customer(client)
    tenant_id = reg["tenant_id"]
    event = MagicMock()
    event.type = "checkout.session.completed"
    event.data.object = _checkout_event(tenant_id)

    with patch(
        "aegis_smb_copilot.billing.stripe_service.stripe.Webhook.construct_event",
        return_value=event,
    ):
        r1 = client.post(
            "/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "sig_ok"},
        )
        r2 = client.post(
            "/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "sig_ok"},
        )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert mock_set_tier.call_count == 1
    mock_set_tier.assert_called_with(uuid.UUID(tenant_id), "paid")


def test_checkout_and_portal_reject_admin_session(client: TestClient) -> None:
    client.post(
        "/auth/admin-login",
        json={"username": "test-admin", "password": "test-admin-password"},
    )
    checkout = client.post("/billing/checkout")
    portal = client.get("/billing/portal")
    assert checkout.status_code == 403
    assert portal.status_code == 403


@patch("aegis_smb_copilot.billing.stripe_service.stripe.checkout.Session.create")
def test_checkout_returns_url_for_customer(
    mock_create: MagicMock,
    client: TestClient,
) -> None:
    _register_customer(client)
    mock_create.return_value = MagicMock(url="https://checkout.stripe.test/session")
    resp = client.post("/billing/checkout")
    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"].startswith("https://checkout.stripe")


@patch("aegis_smb_copilot.billing.stripe_service.stripe.billing_portal.Session.create")
def test_portal_requires_stripe_customer(
    mock_portal: MagicMock,
    client: TestClient,
) -> None:
    _register_customer(client)
    resp = client.get("/billing/portal")
    assert resp.status_code == 400
    assert resp.json()["detail"]["type"] == "no_stripe_customer"

    pool = db_connection.get_pool()
    with pool.connection() as conn:
        conn.execute(
            "UPDATE customers SET stripe_customer_id = %s WHERE email LIKE %s",
            ("cus_existing", "bill-%"),
        )
    mock_portal.return_value = MagicMock(url="https://billing.stripe.test/portal")
    resp2 = client.get("/billing/portal")
    assert resp2.status_code == 200
