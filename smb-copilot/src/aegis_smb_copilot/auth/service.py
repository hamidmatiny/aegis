"""Customer registration, login, and session lifecycle."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from psycopg.errors import UniqueViolation

from aegis_smb_copilot.auth.passwords import hash_password, verify_password
from aegis_smb_copilot.auth.schema import RegisterRequest
from aegis_smb_copilot.auth.sessions import SessionData
from aegis_smb_copilot.billing.policy_files import write_free_tier_override
from aegis_smb_copilot.db.connection import get_pool
from aegis_smb_copilot.tenancy.auth import generate_api_key, hash_api_key

_SLUG_SANITIZE = re.compile(r"[^a-z0-9]+")


def slug_from_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    slug = _SLUG_SANITIZE.sub("-", local).strip("-")
    if not slug or not slug[0].isalnum():
        slug = f"tenant-{slug or 'user'}"
    return slug[:63]


def register_customer(body: RegisterRequest) -> tuple[UUID, str, str, SessionData]:
    """Create tenant + customer row; return tenant_id, slug, api_key (once), session."""
    slug = body.slug or slug_from_email(body.email)
    password_hash = hash_password(body.password)
    api_key = generate_api_key()
    api_digest = hash_api_key(api_key)

    pool = get_pool()
    try:
        with pool.connection() as conn:
            with conn.transaction():
                tenant_row = conn.execute(
                    """
                    INSERT INTO tenants (slug, tier, api_key_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, slug, tier
                    """,
                    (slug, "standard", api_digest),
                ).fetchone()
                if tenant_row is None:
                    raise RuntimeError("tenant insert returned no row")
                tenant_id = tenant_row[0]
                out_slug = str(tenant_row[1])
                conn.execute(
                    """
                    INSERT INTO customers (tenant_id, email, password_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (tenant_id, body.email, password_hash),
                )
    except UniqueViolation as exc:
        constraint = getattr(getattr(exc, "diag", None), "constraint_name", "") or ""
        if "customers_email" in constraint or "email" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": "email_taken", "message": "email is already registered"},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "slug_taken", "message": f"slug {slug!r} is already registered"},
        ) from exc

    write_free_tier_override(out_slug)
    session = SessionData(role="customer", tenant_id=str(tenant_id), email=body.email)
    return tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id)), out_slug, api_key, session


def login_customer(email: str, password: str) -> SessionData:
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT c.password_hash, c.tenant_id, t.slug
            FROM customers c
            JOIN tenants t ON t.id = c.tenant_id
            WHERE c.email = %s
            """,
            (email,),
        ).fetchone()

    if row is None or not verify_password(password, str(row[0])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_credentials", "message": "invalid email or password"},
        )

    return SessionData(role="customer", tenant_id=str(row[1]), email=email)


def login_admin(username: str, password: str) -> SessionData:
    from aegis_smb_copilot import config

    expected_user = config.settings.admin_username
    expected_hash = config.settings.admin_password_hash
    if not expected_user or not expected_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "admin_not_configured", "message": "admin login is not configured"},
        )
    if username != expected_user or not verify_password(password, expected_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_credentials", "message": "invalid username or password"},
        )
    return SessionData(role="admin", username=username)


def customer_me(tenant_id: UUID) -> tuple[str, str, str]:
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT c.email, t.slug, t.tier
            FROM customers c
            JOIN tenants t ON t.id = c.tenant_id
            WHERE c.tenant_id = %s
            """,
            (tenant_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "customer_not_found", "message": "customer record not found"},
        )
    return str(row[0]), str(row[1]), str(row[2])
