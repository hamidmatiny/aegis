"""Admin HTTP routes — operator view of tenants and tier control."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from aegis_smb_copilot.admin import service as admin_service
from aegis_smb_copilot.admin.schema import (
    SetTierRequest,
    TenantDetailResponse,
    TenantListResponse,
)
from aegis_smb_copilot.auth.sessions import SessionData, require_admin_session

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/tenants", response_model=TenantListResponse)
def list_tenants(_admin: SessionData = Depends(require_admin_session)) -> TenantListResponse:
    return admin_service.list_tenants()


@router.get("/tenants/{tenant_id}", response_model=TenantDetailResponse)
def tenant_detail(
    tenant_id: UUID,
    _admin: SessionData = Depends(require_admin_session),
) -> TenantDetailResponse:
    return admin_service.tenant_detail(tenant_id)


@router.post("/tenants/{tenant_id}/tier", status_code=status.HTTP_200_OK)
def set_tier(
    tenant_id: UUID,
    body: SetTierRequest,
    _admin: SessionData = Depends(require_admin_session),
) -> TenantDetailResponse:
    return admin_service.set_tenant_tier(tenant_id, body.tier)
