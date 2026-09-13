"""Admin auth for corp APIs — shared smb session check + internal / read-only tokens."""

from __future__ import annotations

import hmac

from aegis_smb_session.sessions import SessionData, require_admin_session
from fastapi import Depends, Request

from aegis_corp_orchestrator.config import settings

__all__ = [
    "AdminSession",
    "ReadOrAdminSession",
    "SessionData",
    "require_admin",
    "require_read_or_admin",
]


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    return auth.removeprefix("Bearer ").strip()


def require_admin(request: Request) -> SessionData:
    """Full admin: SMB admin cookie or ``AEGIS_INTERNAL_TOKEN`` only.

    Explicitly does **not** accept ``CORP_READONLY_TOKEN`` — POSTs that mutate
    tasks / approve IRREVERSIBLE actions must keep this dependency.
    """
    token = _bearer_token(request)
    if (
        token is not None
        and settings.internal_token
        and hmac.compare_digest(token, settings.internal_token)
    ):
        return SessionData(role="admin", username="internal-token")

    return require_admin_session(request)


def require_read_or_admin(request: Request) -> SessionData:
    """Read path: full admin **or** ``CORP_READONLY_TOKEN`` bearer.

    Use only on GET routes. POSTs must keep ``require_admin``.
    """
    token = _bearer_token(request)
    if (
        token is not None
        and settings.readonly_token
        and hmac.compare_digest(token, settings.readonly_token)
    ):
        return SessionData(role="admin", username="readonly-token")

    return require_admin(request)


AdminSession = Depends(require_admin)
ReadOrAdminSession = Depends(require_read_or_admin)
