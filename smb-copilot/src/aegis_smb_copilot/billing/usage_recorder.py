"""Record local usage_events rows for /qa/ask (Phase 4/5 population).

Receipt *signing* is never done here. When the audit service is reachable we
ask it to sign (POST /v1/receipts) and store the returned receipt_id; if that
fails we still insert the usage row with a NULL audit_receipt_id so
GET /billing/usage can surface a visible discrepancy.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from aegis_smb_copilot import config
from aegis_smb_copilot.db.connection import get_pool

logger = logging.getLogger(__name__)

EVENT_QA_ASK = "qa_ask"
EVENT_WALKTHROUGH_GRANT = "walkthrough_grant"

# Audit service event types (must be in audit ValidEventTypes).
_AUDIT_EVENT_BY_USAGE = {
    EVENT_QA_ASK: "MODEL_ROUTER",
    EVENT_WALKTHROUGH_GRANT: "TOOL_GATE",
}


def _request_signed_receipt(
    *,
    tenant_id: UUID,
    usage_event_type: str,
    client: httpx.Client | None = None,
) -> str | None:
    """Ask audit to sign a receipt; return receipt_id or None on failure."""
    audit_event = _AUDIT_EVENT_BY_USAGE.get(usage_event_type)
    if not audit_event:
        return None

    url = config.settings.audit_service_url.rstrip("/") + "/v1/receipts"
    payload: dict[str, Any] = {
        "event_type": audit_event,
        "tenant_id": str(tenant_id),
        "metadata": {
            "source": "smb-copilot",
            "usage_event_type": usage_event_type,
        },
    }
    headers = {"Content-Type": "application/json"}
    if config.settings.internal_token:
        headers["Authorization"] = f"Bearer {config.settings.internal_token}"

    own = client is None
    http = client or httpx.Client(timeout=10.0)
    try:
        resp = http.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.warning(
                "audit sign failed HTTP %s: %s", resp.status_code, resp.text[:300]
            )
            return None
        body = resp.json()
        rid = body.get("receipt_id") if isinstance(body, dict) else None
        return str(rid) if rid else None
    except Exception as exc:  # noqa: BLE001 — billing path must not fail the ask
        logger.warning("audit sign request failed: %s", exc)
        return None
    finally:
        if own:
            http.close()


def record_usage_event(
    tenant_id: UUID,
    event_type: str,
    *,
    client: httpx.Client | None = None,
) -> UUID:
    """Insert a usage_events row; attach audit_receipt_id when signing succeeds."""
    receipt_id = _request_signed_receipt(
        tenant_id=tenant_id,
        usage_event_type=event_type,
        client=client,
    )
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO usage_events (tenant_id, event_type, audit_receipt_id)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (tenant_id, event_type, receipt_id),
        ).fetchone()
    if row is None:
        raise RuntimeError("usage_events insert returned no row")
    return row[0] if isinstance(row[0], UUID) else UUID(str(row[0]))
