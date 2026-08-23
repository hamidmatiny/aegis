"""Onboarding HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from psycopg.errors import UniqueViolation

from aegis_smb_copilot.onboarding.schema import (
    InfraProfile,
    IntakeRequest,
    RegisterRequest,
    RegisterResponse,
)
from aegis_smb_copilot.onboarding.service import register_tenant, store_intake
from aegis_smb_copilot.tenancy.auth import TenantId

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest) -> RegisterResponse:
    """Create a tenant and issue an API key (returned once)."""
    try:
        return register_tenant(slug=body.slug, tier=body.tier)
    except UniqueViolation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "slug_taken", "message": f"slug {body.slug!r} is already registered"},
        ) from None


@router.post("/intake", response_model=InfraProfile)
def intake(body: IntakeRequest, tenant_id: TenantId) -> InfraProfile:
    """Capture normalized infra profile rows for the authenticated tenant."""
    try:
        return store_intake(tenant_id, body.answers)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "normalization_error", "message": str(exc)},
        ) from exc
