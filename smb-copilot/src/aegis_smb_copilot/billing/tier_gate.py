"""Gate paid features via policy-engine tool evaluation (CEL overrides)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import httpx

from aegis_smb_copilot import config
from aegis_smb_copilot.db.connection import get_pool

WALKTHROUGH_TOOL = "walkthrough"


class PolicyEngineError(RuntimeError):
    """Raised when policy-engine cannot be reached or returns an unexpected body."""


@dataclass(frozen=True)
class TierDecision:
    allowed: bool
    action: str
    tenant_slug: str
    block_reason: str = ""


def resolve_tenant_slug(tenant_id: UUID) -> str:
    """Map auth ``tenant_id`` (UUID) to the policy-engine tenant folder slug."""
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT slug FROM tenants WHERE id = %s",
            (tenant_id,),
        ).fetchone()
    if row is None:
        raise PolicyEngineError(f"tenant {tenant_id} not found")
    return str(row[0])


def check_walkthrough_allowed(
    tenant_id: UUID,
    *,
    client: httpx.Client | None = None,
) -> TierDecision:
    """Ask policy-engine whether this tenant may use the walkthrough feature.

    Calls ``POST /v1/evaluate/tool`` with ``tool_name=walkthrough``. Free-tier
    tenant overrides include a CEL rule that ``block``s that tool; paid tenants
    omit or disable the rule so the pack ``default_action: allow`` wins.
    """
    slug = resolve_tenant_slug(tenant_id)
    url = config.settings.policy_engine_url.rstrip("/") + "/v1/evaluate/tool"
    payload = {
        "tenant_id": slug,
        "mode": "enforce",
        "tool_call": {
            "tool_name": WALKTHROUGH_TOOL,
            "risk_level": "LOW",
            "arguments": [],
        },
    }
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.settings.internal_token:
        headers["Authorization"] = f"Bearer {config.settings.internal_token}"

    own_client = client is None
    http = client or httpx.Client(timeout=10.0)
    try:
        resp = http.post(url, json=payload, headers=headers)
    finally:
        if own_client:
            http.close()

    if resp.status_code >= 400:
        raise PolicyEngineError(
            f"policy-engine evaluate/tool HTTP {resp.status_code}: {resp.text[:500]}"
        )

    body = resp.json()
    decision = body.get("decision") if isinstance(body, dict) else None
    if not isinstance(decision, dict):
        raise PolicyEngineError(f"policy-engine missing decision: {body!r}")

    action = str(decision.get("action") or "").strip().lower()
    if not action:
        raise PolicyEngineError(f"policy-engine decision missing action: {body!r}")

    allowed = action == "allow"
    return TierDecision(
        allowed=allowed,
        action=action,
        tenant_slug=slug,
        block_reason=str(decision.get("block_reason") or ""),
    )
