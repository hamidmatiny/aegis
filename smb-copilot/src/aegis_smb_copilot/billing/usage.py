"""Derive usage summaries from usage_events + audit receipts (integrity cross-check)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from aegis_smb_copilot.billing.audit_client import (
    AuditServiceError,
    fetch_receipts,
    verify_receipt,
)
from aegis_smb_copilot.billing.schema import (
    ReceiptsResponse,
    SignedReceipt,
    UsageDiscrepancy,
    UsageSummaryResponse,
)
from aegis_smb_copilot.billing.usage_recorder import EVENT_QA_ASK, EVENT_WALKTHROUGH_GRANT
from aegis_smb_copilot.db.connection import get_pool


def _parse_bound(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load_usage_rows(
    tenant_id: UUID,
    start: datetime | None,
    end: datetime | None,
) -> list[tuple[UUID, str, UUID | None, datetime]]:
    clauses = ["tenant_id = %s"]
    args: list[object] = [tenant_id]
    if start is not None:
        clauses.append("created_at >= %s")
        args.append(start)
    if end is not None:
        clauses.append("created_at < %s")
        args.append(end)
    sql = (
        "SELECT id, event_type, audit_receipt_id, created_at FROM usage_events WHERE "
        + " AND ".join(clauses)
        + " ORDER BY created_at ASC"
    )
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(sql, tuple(args)).fetchall()
    out: list[tuple[UUID, str, UUID | None, datetime]] = []
    for row in rows:
        eid = row[0] if isinstance(row[0], UUID) else UUID(str(row[0]))
        rid = row[2]
        if rid is not None and not isinstance(rid, UUID):
            rid = UUID(str(rid))
        out.append((eid, str(row[1]), rid, row[3]))
    return out


def build_usage_summary(
    tenant_id: UUID,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
) -> UsageSummaryResponse:
    start = _parse_bound(start_time)
    end = _parse_bound(end_time)
    rows = _load_usage_rows(tenant_id, start, end)

    qa_ask = sum(1 for r in rows if r[1] == EVENT_QA_ASK)
    walkthrough = sum(1 for r in rows if r[1] == EVENT_WALKTHROUGH_GRANT)

    try:
        receipts = fetch_receipts(
            str(tenant_id),
            start_time=start,
            end_time=end,
        )
    except AuditServiceError as exc:
        # Surface every usage row as a discrepancy when audit is unreachable.
        discrepancies = [
            UsageDiscrepancy(
                usage_event_id=r[0],
                event_type=r[1],
                audit_receipt_id=r[2],
                reason=f"audit_unreachable: {exc}",
            )
            for r in rows
        ]
        return UsageSummaryResponse(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            qa_ask_count=qa_ask,
            walkthrough_grant_count=walkthrough,
            usage_events_total=len(rows),
            receipts_matched=0,
            discrepancies=discrepancies,
            integrity="discrepancies_present" if discrepancies else "ok",
        )

    receipt_ids = {r.receipt_id for r in receipts if r.receipt_id}
    matched = 0
    discrepancies: list[UsageDiscrepancy] = []
    for eid, etype, arid, _created in rows:
        if arid is None:
            discrepancies.append(
                UsageDiscrepancy(
                    usage_event_id=eid,
                    event_type=etype,
                    audit_receipt_id=None,
                    reason="missing_audit_receipt_id",
                )
            )
            continue
        if str(arid) not in receipt_ids:
            discrepancies.append(
                UsageDiscrepancy(
                    usage_event_id=eid,
                    event_type=etype,
                    audit_receipt_id=arid,
                    reason="no_matching_signed_receipt",
                )
            )
            continue
        matched += 1

    return UsageSummaryResponse(
        tenant_id=tenant_id,
        start_time=start_time,
        end_time=end_time,
        qa_ask_count=qa_ask,
        walkthrough_grant_count=walkthrough,
        usage_events_total=len(rows),
        receipts_matched=matched,
        discrepancies=discrepancies,
        integrity="discrepancies_present" if discrepancies else "ok",
    )


def list_signed_receipts(
    tenant_id: UUID,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    verify: bool = True,
) -> ReceiptsResponse:
    start = _parse_bound(start_time)
    end = _parse_bound(end_time)
    receipts = fetch_receipts(str(tenant_id), start_time=start, end_time=end)
    signed: list[SignedReceipt] = []
    for r in receipts:
        valid: bool | None = None
        reason = ""
        if verify and r.receipt_id:
            try:
                result = verify_receipt(r.receipt_id)
                valid = result.valid
                reason = result.reason
            except AuditServiceError as exc:
                valid = False
                reason = f"verify_failed: {exc}"
        signed.append(
            SignedReceipt(
                receipt_id=r.receipt_id,
                event_type=r.event_type,
                tenant_id=r.tenant_id,
                created_at=r.created_at,
                signer_key_id=r.signer_key_id,
                signature=r.signature,
                payload_hash=r.payload_hash,
                metadata=r.metadata,
                signature_valid=valid,
                verify_reason=reason,
            )
        )
    return ReceiptsResponse(
        tenant_id=tenant_id,
        start_time=start_time,
        end_time=end_time,
        count=len(signed),
        receipts=signed,
    )
