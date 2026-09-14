"""Redis-backed sessions — thin wrappers over shared aegis_smb_session.

Cookie create/clear still read smb-copilot cookie settings; verify +
require_* are the shared implementation so corp-orchestrator cannot drift.
"""

from __future__ import annotations

from uuid import UUID

from aegis_smb_session.sessions import (
    SESSION_COOKIE,
    SESSION_PREFIX,
    SESSION_TTL_SEC,
    SessionData,
    _verify_signed,
    create_session,
    delete_session,
    get_redis,
    load_session,
    require_admin_session,
    require_customer_session,
    reset_redis_for_tests,
    session_from_request,
)
from aegis_smb_session.sessions import (
    clear_session_cookie as _clear_session_cookie,
)
from aegis_smb_session.sessions import (
    set_session_cookie as _set_session_cookie,
)
from fastapi import HTTPException, Response, status

from aegis_smb_copilot import config

__all__ = [
    "SESSION_COOKIE",
    "SESSION_PREFIX",
    "SESSION_TTL_SEC",
    "SessionData",
    "_verify_signed",
    "clear_session_cookie",
    "create_session",
    "customer_tenant_id",
    "delete_session",
    "get_redis",
    "load_session",
    "require_admin_session",
    "require_customer_session",
    "reset_redis_for_tests",
    "session_from_request",
    "set_session_cookie",
]


def set_session_cookie(response: Response, signed_token: str) -> None:
    _set_session_cookie(
        response,
        signed_token,
        secure=config.settings.cookie_secure,
        path=config.settings.cookie_path,
    )


def clear_session_cookie(response: Response) -> None:
    _clear_session_cookie(response, path=config.settings.cookie_path)


def customer_tenant_id(session: SessionData) -> UUID:
    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_session", "message": "session missing tenant"},
        )
    return UUID(session.tenant_id)
