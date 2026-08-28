"""API-key → tenant authentication (FastAPI dependency).

Mirrors gateway/agent-gate header conventions:
Authorization: Bearer <key> or X-API-Key: <key>.
Keys are stored as SHA-256 hex digests on ``tenants.api_key_hash``.

Customer cookie sessions (``aegis_smb_session``) also resolve to a tenant_id.
Admin sessions are rejected on tenant-scoped routes.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from aegis_smb_copilot.auth.sessions import customer_tenant_id, session_from_request
from aegis_smb_copilot.db.connection import get_pool

API_KEY_PREFIX = "aegis_smb_"


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_hex(32)


def extract_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str | None:
    if authorization:
        prefix = "Bearer "
        if authorization.startswith(prefix):
            return authorization[len(prefix) :].strip() or None
        return authorization.strip() or None
    if x_api_key:
        return x_api_key.strip() or None
    return None


def require_tenant(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> UUID:
    """Resolve customer session or API key to a ``tenant_id``, or raise 401/403."""
    session = session_from_request(request)
    if session is not None:
        if session.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "type": "wrong_role",
                    "message": "admin session cannot access tenant API routes",
                },
            )
        if session.role == "customer":
            return customer_tenant_id(session)

    key = extract_api_key(authorization=authorization, x_api_key=x_api_key)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "aegis_unauthorized",
                "message": (
                    'missing or invalid API key. Send it as "Authorization: Bearer <key>" '
                    'or "X-API-Key: <key>".'
                ),
            },
        )

    digest = hash_api_key(key)
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT id FROM tenants WHERE api_key_hash = %s",
            (digest,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "aegis_unauthorized",
                "message": (
                    'missing or invalid API key. Send it as "Authorization: Bearer <key>" '
                    'or "X-API-Key: <key>".'
                ),
            },
        )

    tenant_id = row[0]
    if not isinstance(tenant_id, UUID):
        tenant_id = UUID(str(tenant_id))
    return tenant_id


TenantId = Annotated[UUID, Depends(require_tenant)]
