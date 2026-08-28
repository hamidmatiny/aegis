"""Admin API models."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from aegis_smb_copilot.billing.schema import UsageSummaryResponse


class TenantSummary(BaseModel):
    id: UUID
    slug: str
    tier: str
    email: str | None = None
    created_at: str
    walkthrough_allowed: bool | None = None


class TenantListResponse(BaseModel):
    tenants: list[TenantSummary]


class TenantDetailResponse(BaseModel):
    id: UUID
    slug: str
    tier: str
    email: str | None = None
    created_at: str
    walkthrough_allowed: bool
    policy_override_path: str
    usage: UsageSummaryResponse


class SetTierRequest(BaseModel):
    tier: Literal["free", "paid"] = Field(description="free blocks walkthrough; paid allows it")
