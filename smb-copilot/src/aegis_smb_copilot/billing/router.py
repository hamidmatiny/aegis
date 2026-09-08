"""Billing HTTP routes — usage summary and signed audit receipts (read path)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from aegis_smb_copilot.billing.audit_client import AuditServiceError
from aegis_smb_copilot.billing.schema import (
    CheckoutResponse,
    PortalResponse,
    ReceiptsResponse,
    UsageSummaryResponse,
)
from aegis_smb_copilot.billing.stripe_service import (
    StripeNotConfiguredError,
    construct_webhook_event,
    create_billing_portal_session,
    create_checkout_session,
    handle_checkout_session_completed,
)
from aegis_smb_copilot.billing.usage import build_usage_summary, list_signed_receipts
from aegis_smb_copilot.tenancy.auth import TenantId

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)


@router.get("/usage", response_model=UsageSummaryResponse)
def get_usage(
    tenant_id: TenantId,
    start_time: str | None = Query(
        default=None,
        description="Inclusive lower bound (RFC3339). Optional.",
    ),
    end_time: str | None = Query(
        default=None,
        description="Exclusive upper bound (RFC3339). Optional.",
    ),
) -> UsageSummaryResponse:
    """Per-tenant usage from usage_events, cross-checked against signed audit receipts.

    Rows without a matching signed receipt appear in ``discrepancies`` (never
    silently dropped).
    """
    try:
        return build_usage_summary(
            tenant_id, start_time=start_time, end_time=end_time
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_time_range", "message": str(exc)},
        ) from exc


@router.get("/receipts", response_model=ReceiptsResponse)
def get_receipts(
    tenant_id: TenantId,
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    verify: bool = Query(
        default=True,
        description="When true, call audit /verify for each receipt (Ed25519 check).",
    ),
) -> ReceiptsResponse:
    """Raw signed audit receipts for this tenant (transparency / dispute)."""
    try:
        return list_signed_receipts(
            tenant_id,
            start_time=start_time,
            end_time=end_time,
            verify=verify,
        )
    except AuditServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "audit_unavailable", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_time_range", "message": str(exc)},
        ) from exc


@router.post("/checkout", response_model=CheckoutResponse)
def start_checkout(tenant_id: TenantId) -> CheckoutResponse:
    """Start Stripe Checkout for a subscription upgrade (customer account required)."""
    try:
        url = create_checkout_session(tenant_id)
    except StripeNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "stripe_not_configured", "message": str(exc)},
        ) from exc
    return CheckoutResponse(checkout_url=url)


@router.get("/portal", response_model=PortalResponse)
def billing_portal(tenant_id: TenantId) -> PortalResponse:
    """Stripe Billing Portal for self-serve subscription management."""
    try:
        url = create_billing_portal_session(tenant_id)
    except StripeNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "stripe_not_configured", "message": str(exc)},
        ) from exc
    return PortalResponse(portal_url=url)


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Stripe webhook — signature verified; upgrades tier on checkout.session.completed."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = construct_webhook_event(payload, signature)
    except StripeNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "stripe_not_configured", "message": str(exc)},
        ) from exc

    if event.type == "checkout.session.completed":
        session = event.data.object
        session_dict = dict(session) if not isinstance(session, dict) else session
        try:
            handle_checkout_session_completed(session_dict)
        except ValueError as exc:
            logger.warning("ignored checkout.session.completed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"type": "invalid_session", "message": str(exc)},
            ) from exc

    return {"status": "ok"}
