"""Read-only typed client for the audit service's signed receipts API.

Signing stays inside the audit service — this module only GETs receipts and
verification results (never POSTs /v1/receipts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from aegis_smb_copilot import config


class AuditServiceError(RuntimeError):
    """Raised when the audit service cannot be reached or returns an unexpected body."""


@dataclass(frozen=True)
class AuditReceipt:
    receipt_id: str
    event_type: str
    tenant_id: str
    created_at: str
    signer_key_id: str
    signature: str
    payload_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerifyResult:
    receipt_id: str
    valid: bool
    reason: str = ""


def _auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = config.settings.internal_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _base_url() -> str:
    return config.settings.audit_service_url.rstrip("/")


def _parse_receipt(row: dict[str, Any]) -> AuditReceipt:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return AuditReceipt(
        receipt_id=str(row.get("receipt_id") or ""),
        event_type=str(row.get("event_type") or ""),
        tenant_id=str(row.get("tenant_id") or ""),
        created_at=str(row.get("created_at") or ""),
        signer_key_id=str(row.get("signer_key_id") or ""),
        signature=str(row.get("signature") or ""),
        payload_hash=str(row.get("payload_hash") or row.get("payload_hash") or ""),
        metadata=dict(meta),
        raw=dict(row),
    )


def fetch_receipts(
    tenant_id: str,
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    event_type: str | None = None,
    limit: int = 200,
    client: httpx.Client | None = None,
) -> list[AuditReceipt]:
    """GET /v1/receipts for ``tenant_id`` within an optional RFC3339 date range.

    Paginates via ``next_cursor`` until exhausted or ``limit`` total rows collected.
    """
    if limit < 1:
        return []

    params: dict[str, str | int] = {
        "tenant_id": tenant_id,
        "limit": min(limit, 200),
    }
    if start_time is not None:
        params["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if end_time is not None:
        params["end_time"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if event_type:
        params["event_type"] = event_type

    url = _base_url() + "/v1/receipts"
    own = client is None
    http = client or httpx.Client(timeout=15.0)
    out: list[AuditReceipt] = []
    try:
        cursor: str | None = None
        while len(out) < limit:
            page_params = dict(params)
            page_params["limit"] = min(200, limit - len(out))
            if cursor:
                page_params["cursor"] = cursor
            resp = http.get(url, params=page_params, headers=_auth_headers())
            if resp.status_code >= 400:
                raise AuditServiceError(
                    f"audit GET /v1/receipts HTTP {resp.status_code}: {resp.text[:500]}"
                )
            body = resp.json()
            if not isinstance(body, dict):
                raise AuditServiceError(f"audit receipts unexpected body: {body!r}")
            rows = body.get("receipts") or []
            if not isinstance(rows, list):
                raise AuditServiceError(f"audit receipts missing list: {body!r}")
            for row in rows:
                if isinstance(row, dict):
                    out.append(_parse_receipt(row))
            cursor = body.get("next_cursor") or None
            if not cursor or not rows:
                break
    finally:
        if own:
            http.close()
    return out


def verify_receipt(
    receipt_id: str,
    *,
    client: httpx.Client | None = None,
) -> VerifyResult:
    """GET /v1/receipts/{id}/verify — Ed25519 + payload-hash check inside audit."""
    url = _base_url() + f"/v1/receipts/{receipt_id}/verify"
    own = client is None
    http = client or httpx.Client(timeout=10.0)
    try:
        resp = http.get(url, headers=_auth_headers())
    finally:
        if own:
            http.close()

    if resp.status_code >= 400:
        raise AuditServiceError(
            f"audit verify HTTP {resp.status_code}: {resp.text[:500]}"
        )
    body = resp.json()
    if not isinstance(body, dict):
        raise AuditServiceError(f"audit verify unexpected body: {body!r}")
    return VerifyResult(
        receipt_id=str(body.get("receipt_id") or receipt_id),
        valid=bool(body.get("valid")),
        reason=str(body.get("reason") or ""),
    )
