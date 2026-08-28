"""Redis-backed sessions with HMAC-signed opaque cookie tokens."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import UUID

import redis
from fastapi import HTTPException, Request, Response, status

from aegis_smb_copilot import config

SESSION_COOKIE = "aegis_smb_session"
SESSION_PREFIX = "smb:session:"
SESSION_TTL_SEC = 60 * 60 * 24 * 7  # 7 days

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(config.settings.redis_url, decode_responses=True)
    return _redis


def reset_redis_for_tests() -> None:
    global _redis
    if _redis is not None:
        _redis.close()
    _redis = None


@dataclass(frozen=True)
class SessionData:
    role: Literal["customer", "admin"]
    tenant_id: str | None = None
    email: str | None = None
    username: str | None = None


def _sign_token(token: str) -> str:
    secret = config.settings.session_secret.encode("utf-8")
    digest = hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{digest}"


def _verify_signed(value: str) -> str | None:
    if "." not in value:
        return None
    token, digest = value.rsplit(".", 1)
    secret = config.settings.session_secret.encode("utf-8")
    expected = hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, expected):
        return None
    return token


def create_session(data: SessionData) -> str:
    token = secrets.token_urlsafe(32)
    payload = json.dumps(asdict(data))
    get_redis().setex(f"{SESSION_PREFIX}{token}", SESSION_TTL_SEC, payload)
    return _sign_token(token)


def load_session(token: str) -> SessionData | None:
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


def delete_session(token: str) -> None:
    get_redis().delete(f"{SESSION_PREFIX}{token}")


def session_from_request(request: Request) -> SessionData | None:
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None
    token = _verify_signed(cookie)
    if token is None:
        return None
    return load_session(token)


def set_session_cookie(response: Response, signed_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=signed_token,
        httponly=True,
        secure=config.settings.cookie_secure,
        samesite="lax",
        max_age=SESSION_TTL_SEC,
        path=config.settings.cookie_path,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path=config.settings.cookie_path,
    )


def require_customer_session(request: Request) -> SessionData:
    session = session_from_request(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "not_authenticated", "message": "customer login required"},
        )
    if session.role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"type": "wrong_role", "message": "customer session required"},
        )
    if not session.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_session", "message": "session missing tenant"},
        )
    return session


def require_admin_session(request: Request) -> SessionData:
    session = session_from_request(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "not_authenticated", "message": "admin login required"},
        )
    if session.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"type": "wrong_role", "message": "admin session required"},
        )
    return session


def customer_tenant_id(session: SessionData) -> UUID:
    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_session", "message": "session missing tenant"},
        )
    return UUID(session.tenant_id)
