"""Admin tenant listing and tier management."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from aegis_smb_copilot.admin.schema import TenantDetailResponse, TenantListResponse, TenantSummary
from aegis_smb_copilot.billing.policy_files import (
    reload_policy_engine,
    set_walkthrough_tier,
    tenants_policy_dir,
)
from aegis_smb_copilot.billing.tier_gate import PolicyEngineError, check_walkthrough_allowed
from aegis_smb_copilot.billing.usage import build_usage_summary
from aegis_smb_copilot.db.connection import get_pool


def _walkthrough_status(tenant_id: UUID) -> bool | None:
    try:
        return check_walkthrough_allowed(tenant_id).allowed
    except PolicyEngineError:
        return None


def list_tenants() -> TenantListResponse:
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.slug, t.tier, t.created_at, c.email
            FROM tenants t
            LEFT JOIN customers c ON c.tenant_id = t.id
            ORDER BY t.created_at DESC
            """
        ).fetchall()

    tenants: list[TenantSummary] = []
    for row in rows:
        tenant_id = row[0] if isinstance(row[0], UUID) else UUID(str(row[0]))
        tenants.append(
            TenantSummary(
                id=tenant_id,
                slug=str(row[1]),
                tier=str(row[2]),
                created_at=row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                email=str(row[4]) if row[4] else None,
                walkthrough_allowed=_walkthrough_status(tenant_id),
            )
        )
    return TenantListResponse(tenants=tenants)


def tenant_detail(tenant_id: UUID) -> TenantDetailResponse:
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT t.id, t.slug, t.tier, t.created_at, c.email
            FROM tenants t
            LEFT JOIN customers c ON c.tenant_id = t.id
            WHERE t.id = %s
            """,
            (tenant_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "tenant_not_found", "message": "tenant not found"},
        )

    slug = str(row[1])
    override_path = str(tenants_policy_dir() / slug / "overrides.yaml")
    try:
        walkthrough_allowed = check_walkthrough_allowed(tenant_id).allowed
    except PolicyEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "policy_engine_unavailable", "message": str(exc)},
        ) from exc

    usage = build_usage_summary(tenant_id)
    return TenantDetailResponse(
        id=tenant_id,
        slug=slug,
        tier=str(row[2]),
        email=str(row[4]) if row[4] else None,
        created_at=row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        walkthrough_allowed=walkthrough_allowed,
        policy_override_path=override_path,
        usage=usage,
    )


def set_tenant_tier(tenant_id: UUID, tier: str) -> TenantDetailResponse:
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT slug FROM tenants WHERE id = %s",
            (tenant_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "tenant_not_found", "message": "tenant not found"},
        )

    slug = str(row[0])
    paid = tier == "paid"
    set_walkthrough_tier(slug, paid=paid)
    try:
        reload_policy_engine()
    except PolicyEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "policy_reload_failed", "message": str(exc)},
        ) from exc

    db_tier = "premium" if paid else "standard"
    with pool.connection() as conn:
        conn.execute(
            "UPDATE tenants SET tier = %s WHERE id = %s",
            (db_tier, tenant_id),
        )

    return tenant_detail(tenant_id)
