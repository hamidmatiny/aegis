"""Q&A endpoint tests (Postgres + Redis; model-router mocked)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch
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
    """Build a host-side Redis URL using compose credentials from .env."""
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
os.environ["SMB_QA_RATE_LIMIT"] = "2"
os.environ["SMB_QA_RATE_WINDOW_SEC"] = "60"
os.environ.setdefault(
    "AEGIS_POLICY_TENANTS_DIR",
    str(Path(__file__).resolve().parents[2] / ".pytest_policy_tenants"),
)

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aegis_smb_copilot import config as config_mod
from aegis_smb_copilot.db import connection as db_connection
from aegis_smb_copilot.qa import rate_limit as rate_limit_mod
from aegis_smb_copilot.qa.schema import QA_DISCLAIMER, AskResponse

Path(os.environ["AEGIS_POLICY_TENANTS_DIR"]).mkdir(parents=True, exist_ok=True)
config_mod.settings = config_mod.Settings()
rate_limit_mod.reset_redis_for_tests()

from aegis_smb_copilot.main import app
from aegis_smb_copilot.onboarding.service import store_intake
from aegis_smb_copilot.onboarding.schema import IntakeAnswer
from aegis_smb_copilot.qa.cve_match import match_cves
from aegis_smb_copilot.qa.retrieval import retrieve_infra_context
from aegis_smb_copilot.qa.service import ask
from aegis_smb_copilot.tenancy.auth import generate_api_key, hash_api_key


def _fake_embed(texts: list[str], **_k: object) -> list[list[float]]:
    out: list[list[float]] = []
    for i, text in enumerate(texts):
        vec = [0.0] * 1536
        # Make "postgres" questions closer to postgres infra rows.
        if "postgres" in text.lower() or "database:postgres" in text.lower():
            vec[0] = 1.0
        if "eks" in text.lower() or "cloud:aws-eks" in text.lower():
            vec[1] = 1.0
        vec[2] = float(len(text) % 100) / 100.0
        vec[3] = float(i)
        out.append(vec)
    return out


def _deps_ready() -> bool:
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
                conn.execute("SELECT 1 FROM cve_reference LIMIT 0")
                conn.execute("SELECT embedding FROM infra_memory LIMIT 0")
        finally:
            pool.close()
        client = rate_limit_mod.get_redis()
        client.ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _deps_ready(),
    reason="Postgres (cve_reference) and Redis not available for Q&A tests",
)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    db_connection.close_pool()
    rate_limit_mod.reset_redis_for_tests()
    with TestClient(app) as test_client:
        yield test_client
    db_connection.close_pool()
    rate_limit_mod.reset_redis_for_tests()


def test_disclaimer_required_non_empty() -> None:
    with pytest.raises(ValidationError):
        AskResponse(answer="ok", disclaimer="")
    ok = AskResponse(answer="ok", disclaimer=QA_DISCLAIMER)
    assert ok.disclaimer == QA_DISCLAIMER
    assert len(ok.disclaimer.strip()) > 0


def test_cve_match_flags_seeded_postgres() -> None:
    hits = match_cves(["postgres-16.2.x", "unrelated-thing"])
    assert any(h.cve_id == "CVE-2024-10979" for h in hits)
    assert all(h.matched_value in {"postgres-16.2.x"} for h in hits)


@patch("aegis_smb_copilot.qa.retrieval.embed_texts", side_effect=_fake_embed)
@patch("aegis_smb_copilot.onboarding.service.embed_texts", side_effect=_fake_embed)
def test_retrieval_scoped_to_tenant(_e1: object, _e2: object) -> None:
    pool = db_connection.get_pool()
    slug_a = f"qa-a-{uuid.uuid4().hex[:8]}"
    slug_b = f"qa-b-{uuid.uuid4().hex[:8]}"
    with pool.connection() as conn:
        a = conn.execute(
            "INSERT INTO tenants (slug, tier, api_key_hash) VALUES (%s,'standard',%s) RETURNING id",
            (slug_a, hash_api_key(generate_api_key())),
        ).fetchone()
        b = conn.execute(
            "INSERT INTO tenants (slug, tier, api_key_hash) VALUES (%s,'standard',%s) RETURNING id",
            (slug_b, hash_api_key(generate_api_key())),
        ).fetchone()
    assert a and b
    tenant_a, tenant_b = a[0], b[0]
    store_intake(tenant_a, [IntakeAnswer(category="database", value="PostgreSQL 16.2")])
    store_intake(tenant_b, [IntakeAnswer(category="cloud", value="AWS EKS")])

    rows = retrieve_infra_context(tenant_a, "How do I harden postgres?")
    assert rows
    assert all(
        # retrieval does not return tenant_id; ensure values belong to A by querying
        True
        for _ in rows
    )
    with pool.connection() as conn:
        for row in rows:
            owner = conn.execute(
                "SELECT tenant_id FROM infra_memory WHERE id = %s",
                (row.id,),
            ).fetchone()
            assert owner is not None and owner[0] == tenant_a


@patch("aegis_smb_copilot.qa.service.chat_completion", return_value="Advisory answer.")
@patch("aegis_smb_copilot.qa.retrieval.embed_texts", side_effect=_fake_embed)
@patch("aegis_smb_copilot.onboarding.service.embed_texts", side_effect=_fake_embed)
def test_ask_passes_token_cap_and_model_by_tier(
    _e1: object, _e2: object, mock_chat: object
) -> None:
    pool = db_connection.get_pool()
    slug = f"qa-cap-{uuid.uuid4().hex[:8]}"
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO tenants (slug, tier, api_key_hash) VALUES (%s,'standard',%s) RETURNING id",
            (slug, hash_api_key(generate_api_key())),
        ).fetchone()
    assert row is not None
    tenant_id = row[0]
    store_intake(tenant_id, [IntakeAnswer(category="database", value="PostgreSQL 16.2")])

    config_mod.settings = config_mod.Settings(
        SMB_QA_MAX_TOKENS_FREE=500,
        SMB_QA_MAX_TOKENS_WALKTHROUGH=1200,
        SMB_CHAT_MODEL="grok-4-fast",
        SMB_CHAT_MODEL_WALKTHROUGH="grok-4",
    )

    ask(tenant_id, "Free question?")
    free_call = mock_chat.call_args
    assert free_call.kwargs["max_tokens"] == 500
    assert free_call.kwargs["model"] == "grok-4-fast"

    ask(tenant_id, "Walk me through hardening", walkthrough=True)
    paid_call = mock_chat.call_args
    assert paid_call.kwargs["max_tokens"] == 1200
    assert paid_call.kwargs["model"] == "grok-4"


@patch("aegis_smb_copilot.qa.service.chat_completion", return_value="Advisory answer.")
@patch("aegis_smb_copilot.qa.retrieval.embed_texts", side_effect=_fake_embed)
@patch("aegis_smb_copilot.onboarding.service.embed_texts", side_effect=_fake_embed)
def test_ask_includes_mandatory_disclaimer(
    _e1: object, _e2: object, _chat: object
) -> None:
    pool = db_connection.get_pool()
    slug = f"qa-ask-{uuid.uuid4().hex[:8]}"
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO tenants (slug, tier, api_key_hash) VALUES (%s,'standard',%s) RETURNING id",
            (slug, hash_api_key(generate_api_key())),
        ).fetchone()
    assert row is not None
    tenant_id = row[0]
    store_intake(tenant_id, [IntakeAnswer(category="database", value="PostgreSQL 16.2")])

    resp = ask(tenant_id, "Are there postgres risks?")
    assert resp.disclaimer == QA_DISCLAIMER
    assert resp.disclaimer.strip()
    assert "Advisory" in resp.answer or resp.answer
    assert any(c.cve_id == "CVE-2024-10979" for c in resp.cve_matches)


@patch("aegis_smb_copilot.qa.service.chat_completion", return_value="ok")
@patch("aegis_smb_copilot.qa.retrieval.embed_texts", side_effect=_fake_embed)
@patch("aegis_smb_copilot.onboarding.service.embed_texts", side_effect=_fake_embed)
def test_ask_rate_limited_returns_429(
    _e1: object, _e2: object, _chat: object, client: TestClient
) -> None:
    slug = f"qa-rl-{uuid.uuid4().hex[:8]}"
    reg = client.post("/onboarding/register", json={"slug": slug})
    assert reg.status_code == 201
    key = reg.json()["api_key"]
    tenant_id = reg.json()["tenant_id"]

    # Clear any prior counter for this tenant.
    rate_limit_mod.get_redis().delete(f"smb:qa:rl:{tenant_id}")

    headers = {"Authorization": f"Bearer {key}"}
    body = {"question": "What should I patch first?"}

    r1 = client.post("/qa/ask", headers=headers, json=body)
    r2 = client.post("/qa/ask", headers=headers, json=body)
    r3 = client.post("/qa/ask", headers=headers, json=body)

    assert r1.status_code == 200, r1.text
    assert r1.json()["disclaimer"] == QA_DISCLAIMER
    assert r2.status_code == 200, r2.text
    assert r3.status_code == 429, r3.text
    assert r3.json()["detail"]["type"] == "rate_limit_exceeded"
