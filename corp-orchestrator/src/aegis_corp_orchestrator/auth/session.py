"""Redis-backed admin session verification (shared with smb-copilot cookies)."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Literal

import redis
from fastapi import Depends, HTTPException, Request, status

from aegis_corp_orchestrator.config import settings

SESSION_COOKIE = "aegis_smb_session"
SESSION_PREFIX = "smb:session:"

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


@dataclass(frozen=True)
class SessionData:
    role: Literal["customer", "admin"]
    tenant_id: str | None = None
    email: str | None = None
    username: str | None = None


def _verify_signed(value: str) -> str | None:
    if "." not in value:
        return None
    token, digest = value.rsplit(".", 1)
    secret = settings.session_secret.encode("utf-8")
    expected = hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, expected):
        return None
    return token


def session_from_request(request: Request) -> SessionData | None:
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None
    token = _verify_signed(cookie)
    if token is None:
        return None
    raw = get_redis().get(f"{SESSION_PREFIX}{token}")
    if raw is None:
        return None
    parsed = json.loads(raw)
    return SessionData(
        role=parsed["role"],
        tenant_id=parsed.get("tenant_id"),
        email=parsed.get("email"),
        username=parsed.get("username"),
    )


def require_admin(request: Request) -> SessionData:
    # Ops/automation: same internal token used by other AEGIS services.
    auth = request.headers.get("Authorization") or ""
    if (
        auth.startswith("Bearer ")
        and settings.internal_token
        and hmac.compare_digest(auth.removeprefix("Bearer ").strip(), settings.internal_token)
    ):
        return SessionData(role="admin", username="internal-token")

    session = session_from_request(request)
    if session is None or session.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "admin_required", "message": "admin session required"},
        )
    return session


AdminSession = Depends(require_admin)
