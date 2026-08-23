"""Q&A HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from aegis_smb_copilot.qa.rate_limit import RateLimitExceeded, enforce_qa_rate_limit
from aegis_smb_copilot.qa.schema import AskRequest, AskResponse
from aegis_smb_copilot.qa.service import ask
from aegis_smb_copilot.tenancy.auth import TenantId

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask", response_model=AskResponse)
def ask_question(body: AskRequest, tenant_id: TenantId) -> AskResponse:
    """Retrieve tenant infra context and return advisory text (no actions)."""
    try:
        enforce_qa_rate_limit(tenant_id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "type": "rate_limit_exceeded",
                "message": str(exc),
                "limit": exc.limit,
                "window_sec": exc.window_sec,
            },
        ) from exc

    return ask(tenant_id, body.question)
