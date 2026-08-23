"""Billing HTTP routes — usage summary and signed audit receipts (read path)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from aegis_smb_copilot.billing.audit_client import AuditServiceError
from aegis_smb_copilot.billing.schema import ReceiptsResponse, UsageSummaryResponse
from aegis_smb_copilot.billing.usage import build_usage_summary, list_signed_receipts
from aegis_smb_copilot.tenancy.auth import TenantId

router = APIRouter(prefix="/billing", tags=["billing"])


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
