"""Admin auth for corp APIs — shared smb session check + internal token."""

from __future__ import annotations

import hmac

from aegis_smb_session.sessions import SessionData, require_admin_session
from fastapi import Depends, HTTPException, Request, status

from aegis_corp_orchestrator.config import settings

__all__ = ["AdminSession", "SessionData", "require_admin"]


def require_admin(request: Request) -> SessionData:
    # Ops/automation: same internal token used by other AEGIS services.
    auth = request.headers.get("Authorization") or ""
    if (
        auth.startswith("Bearer ")
        and settings.internal_token
        and hmac.compare_digest(auth.removeprefix("Bearer ").strip(), settings.internal_token)
    ):
        return SessionData(role="admin", username="internal-token")

    return require_admin_session(request)


AdminSession = Depends(require_admin)
