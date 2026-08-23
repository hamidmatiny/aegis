"""Q&A HTTP routes."""

from __future__ import annotations

from typing import Union

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from aegis_smb_copilot.billing.tier_gate import PolicyEngineError, check_walkthrough_allowed
from aegis_smb_copilot.qa.rate_limit import RateLimitExceeded, enforce_qa_rate_limit
from aegis_smb_copilot.qa.schema import AskRequest, AskResponse, WalkthroughUpsellResponse
from aegis_smb_copilot.qa.service import ask
from aegis_smb_copilot.tenancy.auth import TenantId

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post(
    "/ask",
    response_model=None,
    responses={
        200: {
            "description": "Advisory answer or structured walkthrough upsell",
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/AskResponse"},
                            {"$ref": "#/components/schemas/WalkthroughUpsellResponse"},
                        ]
                    }
                }
            },
        },
        429: {"description": "Per-tenant rate limit exceeded"},
    },
)
def ask_question(
    body: AskRequest, tenant_id: TenantId
) -> Union[AskResponse, WalkthroughUpsellResponse, JSONResponse]:
    """Retrieve tenant infra context and return advisory text (no actions).

    When ``walkthrough=true``, policy-engine must allow tool ``walkthrough`` for
    this tenant's slug; otherwise return a structured upsell body (not a bare 403).
    """
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

    if body.walkthrough:
        try:
            decision = check_walkthrough_allowed(tenant_id)
        except PolicyEngineError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "type": "policy_engine_unavailable",
                    "message": str(exc),
                },
            ) from exc
        if not decision.allowed:
            return WalkthroughUpsellResponse(policy_action=decision.action)

    return ask(tenant_id, body.question, walkthrough=body.walkthrough)
