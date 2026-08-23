"""Billing usage summary and receipt response models."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UsageDiscrepancy(BaseModel):
    """A usage_events row that cannot be trusted against signed audit receipts."""

    usage_event_id: UUID
    event_type: str
    audit_receipt_id: UUID | None = None
    reason: str


class UsageSummaryResponse(BaseModel):
    tenant_id: UUID
    start_time: str | None = None
    end_time: str | None = None
    qa_ask_count: int
    walkthrough_grant_count: int
    usage_events_total: int
    receipts_matched: int
    discrepancies: list[UsageDiscrepancy] = Field(default_factory=list)
    integrity: Literal["ok", "discrepancies_present"]


class SignedReceipt(BaseModel):
    receipt_id: str
    event_type: str
    tenant_id: str
    created_at: str
    signer_key_id: str
    signature: str
    payload_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    signature_valid: bool | None = None
    verify_reason: str = ""


class ReceiptsResponse(BaseModel):
    tenant_id: UUID
    start_time: str | None = None
    end_time: str | None = None
    count: int
    receipts: list[SignedReceipt]
