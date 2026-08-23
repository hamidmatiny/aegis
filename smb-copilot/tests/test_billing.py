"""Billing / tier-gate tests (policy-engine mocked; Postgres for register)."""

from __future__ import annotations

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
            if line.startswith("REDIS_URL="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                parsed = urlparse(raw)
                if parsed.password:
                    pwd = parsed.password
    return f"redis://:{pwd}@127.0.0.1:6379/0"


os.environ["DATABASE_URL"] = _host_database_url()
os.environ["REDIS_URL"] = _host_redis_url()
os.environ["SMB_QA_RATE_LIMIT"] = "20"
os.environ["SMB_QA_RATE_WINDOW_SEC"] = "60"

import pytest
from fastapi.testclient import TestClient

from aegis_smb_copilot import config as config_mod
from aegis_smb_copilot.billing.policy_files import (
    SMB_DENY_WALKTHROUGH_RULE_ID,
    free_tier_overrides_yaml,
    write_free_tier_override,
)
from aegis_smb_copilot.billing.tier_gate import TierDecision, check_walkthrough_allowed
from aegis_smb_copilot.db import connection as db_connection
from aegis_smb_copilot.qa import rate_limit as rate_limit_mod
from aegis_smb_copilot.tenancy.auth import generate_api_key, hash_api_key


@pytest.fixture()
def policy_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tenants = tmp_path / "tenants"
    tenants.mkdir()
    monkeypatch.setenv("AEGIS_POLICY_TENANTS_DIR", str(tenants))
    config_mod.settings = config_mod.Settings()
    return tenants


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
                conn.execute("SELECT api_key_hash FROM tenants LIMIT 0")
        finally:
            pool.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_ready(),
    reason="Postgres with SMB schema not available",
)


@pytest.fixture()
def client(policy_dir: Path) -> Iterator[TestClient]:
    db_connection.close_pool()
    rate_limit_mod.reset_redis_for_tests()
    with TestClient(app) as test_client:
        yield test_client
    db_connection.close_pool()


# Import app after settings/env are configured for this module.
from aegis_smb_copilot.main import app  # noqa: E402


def test_free_tier_yaml_contains_deny_rule() -> None:
    text = free_tier_overrides_yaml("acme-demo")
    assert "extends: default" in text
    assert "tenant_id: acme-demo" in text
    assert SMB_DENY_WALKTHROUGH_RULE_ID in text
    assert 'cel: "tool_call.tool_name == \'walkthrough\'"' in text
    assert "action: block" in text
    assert "enabled: true" in text


def test_write_free_tier_override(policy_dir: Path) -> None:
    path = write_free_tier_override("demo-tenant")
    assert path == policy_dir / "demo-tenant" / "overrides.yaml"
    assert path.is_file()
    assert "smb-deny-walkthrough" in path.read_text(encoding="utf-8")


def test_register_writes_policy_override(client: TestClient, policy_dir: Path) -> None:
    slug = f"bill-{uuid.uuid4().hex[:10]}"
    reg = client.post("/onboarding/register", json={"slug": slug, "tier": "standard"})
    assert reg.status_code == 201, reg.text
    override = policy_dir / slug / "overrides.yaml"
    assert override.is_file()
    body = override.read_text(encoding="utf-8")
    assert f"tenant_id: {slug}" in body
    assert "enabled: true" in body


def test_walkthrough_denied_returns_upsell(client: TestClient) -> None:
    slug = f"free-{uuid.uuid4().hex[:10]}"
    reg = client.post("/onboarding/register", json={"slug": slug})
    assert reg.status_code == 201
    api_key = reg.json()["api_key"]

    denied = TierDecision(
        allowed=False,
        action="block",
        tenant_slug=slug,
        block_reason="smb-deny-walkthrough",
    )
    with (
        patch(
            "aegis_smb_copilot.qa.router.check_walkthrough_allowed",
            return_value=denied,
        ),
        patch(
            "aegis_smb_copilot.qa.service.chat_completion",
            side_effect=AssertionError("chat must not run on upsell"),
        ),
    ):
        resp = client.post(
            "/qa/ask",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"question": "How do I harden postgres?", "walkthrough": True},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "upsell"
    assert data["feature"] == "walkthrough"
    assert data["message"]
    assert data["upgrade_hint"]
    assert data["policy_action"] == "block"
    assert "disclaimer" not in data or data.get("disclaimer")  # upsell has no answer path


def test_walkthrough_allowed_returns_answer(client: TestClient) -> None:
    slug = f"paid-{uuid.uuid4().hex[:10]}"
    reg = client.post("/onboarding/register", json={"slug": slug})
    assert reg.status_code == 201
    api_key = reg.json()["api_key"]
    tenant_id = uuid.UUID(reg.json()["tenant_id"])

    allowed = TierDecision(allowed=True, action="allow", tenant_slug=slug)
    with (
        patch(
            "aegis_smb_copilot.qa.router.check_walkthrough_allowed",
            return_value=allowed,
        ),
        patch(
            "aegis_smb_copilot.qa.service.retrieve_infra_context",
            return_value=[],
        ),
        patch(
            "aegis_smb_copilot.qa.service.match_cves",
            return_value=[],
        ),
        patch(
            "aegis_smb_copilot.qa.service.chat_completion",
            return_value="1. Backup\n2. Patch\n3. Verify",
        ),
    ):
        resp = client.post(
            "/qa/ask",
            headers={"X-API-Key": api_key},
            json={"question": "Walk me through hardening", "walkthrough": True},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "answer"
    assert data["walkthrough"] is True
    assert data["answer"].startswith("1.")
    assert len(data["disclaimer"].strip()) > 0
    assert str(tenant_id)  # used registration


def test_plain_ask_skips_tier_gate(client: TestClient) -> None:
    slug = f"plain-{uuid.uuid4().hex[:10]}"
    reg = client.post("/onboarding/register", json={"slug": slug})
    api_key = reg.json()["api_key"]

    with (
        patch(
            "aegis_smb_copilot.qa.router.check_walkthrough_allowed",
            side_effect=AssertionError("tier gate must not run for plain ask"),
        ),
        patch(
            "aegis_smb_copilot.qa.service.retrieve_infra_context",
            return_value=[],
        ),
        patch(
            "aegis_smb_copilot.qa.service.match_cves",
            return_value=[],
        ),
        patch(
            "aegis_smb_copilot.qa.service.chat_completion",
            return_value="Use parameterized queries.",
        ),
    ):
        resp = client.post(
            "/qa/ask",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"question": "How do I avoid SQL injection?"},
        )
    assert resp.status_code == 200
    assert resp.json()["type"] == "answer"
    assert resp.json()["walkthrough"] is False


def test_check_walkthrough_calls_policy_engine(policy_dir: Path) -> None:
    slug = f"gate-{uuid.uuid4().hex[:8]}"
    digest = hash_api_key(generate_api_key())
    pool = db_connection.get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO tenants (slug, tier, api_key_hash) VALUES (%s, %s, %s) RETURNING id",
            (slug, "standard", digest),
        ).fetchone()
    tenant_id = row[0]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "decision": {"action": "block", "block_reason": "smb-deny-walkthrough"}
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp

    decision = check_walkthrough_allowed(tenant_id, client=mock_client)
    assert decision.allowed is False
    assert decision.action == "block"
    assert decision.tenant_slug == slug

    args, kwargs = mock_client.post.call_args
    assert args[0].endswith("/v1/evaluate/tool")
    assert kwargs["json"]["tenant_id"] == slug
    assert kwargs["json"]["tool_call"]["tool_name"] == "walkthrough"
    assert "headers" in kwargs

