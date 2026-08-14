"""Shared internal service-to-service token enforcement.

This service had no auth of its own beyond Docker network isolation --
anything that could reach its port could call it directly. AEGIS_INTERNAL_TOKEN
is a single secret shared by every internal-only service (policy-engine,
audit, input-defense, output-defense) and the handful of processes that
call them (gateway, agent-gate, redteam, the dashboard's nginx proxy) --
see scripts/generate-credentials.sh and docker-compose.yml.
"""

from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

# Liveness/readiness probes must stay reachable for container
# orchestration health checks, same exemption as every other AEGIS auth
# surface (gateway, agent-gate, and the two Go internal services).
EXEMPT_PATHS = {"/health", "/ready"}


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header:
        if header.startswith("Bearer "):
            return header[len("Bearer ") :]
        return header
    return request.headers.get("x-aegis-internal-token", "")


def _valid(configured: str, candidate: str) -> bool:
    if not configured or not candidate:
        return False
    return hmac.compare_digest(configured, candidate)


class InternalTokenMiddleware(BaseHTTPMiddleware):
    """Rejects any request that doesn't carry the shared internal token,
    except EXEMPT_PATHS. token must be non-empty -- callers should refuse
    to start the app at all if AEGIS_INTERNAL_TOKEN is unset (see app.py)
    rather than run open or generate a per-process fallback, since that
    would desync from every other service's copy of the same secret.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        if not _valid(self._token, _extract_token(request)):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "type": "aegis_unauthorized",
                        "message": (
                            "missing or invalid internal service token. Send it as "
                            '"Authorization: Bearer <token>" or "X-Aegis-Internal-Token: <token>".'
                        ),
                    }
                },
            )
        return await call_next(request)
