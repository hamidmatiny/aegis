"""Onboarding auth + intake integration tests (requires Postgres)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def _host_database_url() -> str:
    """Use compose credentials but point at published 127.0.0.1:5432."""
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or "postgres" == urlparse(raw).hostname:
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


os.environ["DATABASE_URL"] = _host_database_url()

import pytest
from fastapi.testclient import TestClient

from aegis_smb_copilot import config as config_mod
from aegis_smb_copilot.db import connection as db_connection

# Settings may have been imported elsewhere; re-bind from the forced env.
config_mod.settings = config_mod.Settings()

from aegis_smb_copilot.main import app
from aegis_smb_copilot.onboarding.service import normalize_pair


def _postgres_ready() -> bool:
    try:
        db_connection.close_pool()
        # Avoid long pool retry loops when Postgres is down.
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
                conn.execute("SELECT embedding FROM infra_memory LIMIT 0")
        finally:
            pool.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_ready(),
    reason="Postgres with SMB schema (api_key_hash, nullable embedding) not available",
)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    db_connection.close_pool()
    with TestClient(app) as test_client:
        yield test_client
    db_connection.close_pool()


def test_normalize_database_major_minor() -> None:
    cat, val = normalize_pair("database", "PostgreSQL 16.2")
    assert cat == "database"
    assert val == "postgres-16.2.x"


def test_normalize_major_only() -> None:
    cat, val = normalize_pair("database", "postgres 16")
    assert cat == "database"
    assert val == "postgres-16.x"


def test_intake_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/onboarding/intake",
        json={"answers": [{"category": "database", "value": "postgres 16"}]},
    )
    assert resp.status_code == 401


def test_register_and_intake_scoped_to_tenant(client: TestClient) -> None:
    slug = f"acme-{uuid.uuid4().hex[:10]}"
    reg = client.post("/onboarding/register", json={"slug": slug, "tier": "standard"})
    assert reg.status_code == 201, reg.text
    body = reg.json()
    tenant_id = body["tenant_id"]
    api_key = body["api_key"]
    assert api_key.startswith("aegis_smb_")

    intake = client.post(
        "/onboarding/intake",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "answers": [
                {"category": "database", "value": "PostgreSQL 16.2"},
                {"category": "cloud", "value": "AWS EKS"},
            ]
        },
    )
    assert intake.status_code == 200, intake.text
    profile = intake.json()
    assert profile["tenant_id"] == tenant_id
    assert len(profile["items"]) == 2
    norms = {i["category"]: i["normalized_value"] for i in profile["items"]}
    assert norms["database"] == "postgres-16.2.x"

    pool = db_connection.get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT tenant_id, category, normalized_value, embedding "
            "FROM infra_memory WHERE tenant_id = %s ORDER BY category",
            (tenant_id,),
        ).fetchall()
    assert len(rows) == 2
    for row in rows:
        assert str(row[0]) == tenant_id
        assert row[3] is None  # embeddings deferred to Phase 3

    other = client.post(
        "/onboarding/register",
        json={"slug": f"other-{uuid.uuid4().hex[:10]}"},
    )
    assert other.status_code == 201
    other_id = other.json()["tenant_id"]
    with pool.connection() as conn:
        leaked = conn.execute(
            "SELECT COUNT(*) FROM infra_memory WHERE tenant_id = %s",
            (other_id,),
        ).fetchone()
    assert leaked is not None and leaked[0] == 0

    bad = client.post(
        "/onboarding/intake",
        headers={"X-API-Key": "aegis_smb_" + "00" * 32},
        json={"answers": [{"category": "database", "value": "mysql 8"}]},
    )
    assert bad.status_code == 401
