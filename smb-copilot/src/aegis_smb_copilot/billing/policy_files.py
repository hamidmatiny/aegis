"""Write per-tenant policy-engine override YAML (free tier by default)."""

from __future__ import annotations

from pathlib import Path

import httpx
import yaml

from aegis_smb_copilot import config
from aegis_smb_copilot.billing.tier_gate import PolicyEngineError

# Rule id used in free-tier YAML; flip enabled:false (or remove the rule) for paid.
SMB_DENY_WALKTHROUGH_RULE_ID = "smb-deny-walkthrough"

_FREE_TIER_TEMPLATE = """\
# SMB Copilot free tier — generated at tenant registration.
# Flip smb-deny-walkthrough to enabled: false (or remove the rule) for paid.
# Then POST http://localhost:8081/v1/reload (or wait for auto-reload).
extends: default
id: default
version: "0.1.0-smb-free"
tenant_id: {slug}
description: SMB Copilot free tier for {slug} — guided walkthrough denied

tool_rules:
  - id: {rule_id}
    name: Free tier blocks guided walkthrough
    cel: "tool_call.tool_name == 'walkthrough'"
    action: block
    enabled: true

settings:
  default_action: allow
"""


def tenants_policy_dir() -> Path:
    return Path(config.settings.policy_tenants_dir)


def free_tier_overrides_yaml(slug: str) -> str:
    return _FREE_TIER_TEMPLATE.format(
        slug=slug,
        rule_id=SMB_DENY_WALKTHROUGH_RULE_ID,
    )


def write_free_tier_override(slug: str) -> Path:
    """Create ``policies/tenants/<slug>/overrides.yaml`` defaulting to free tier.

    Policy-engine loads this directory by folder name as ``tenant_id`` and
    merges it onto the base pack (see policy-engine README / loader.Resolve).
    """
    dest_dir = tenants_policy_dir() / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "overrides.yaml"
    dest.write_text(free_tier_overrides_yaml(slug), encoding="utf-8")
    return dest


def set_walkthrough_tier(slug: str, *, paid: bool) -> Path:
    """Enable or disable walkthrough for a tenant via the existing override file."""
    dest = tenants_policy_dir() / slug / "overrides.yaml"
    if not dest.is_file():
        write_free_tier_override(slug)

    raw = yaml.safe_load(dest.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raw = {}

    rules = raw.get("tool_rules")
    if not isinstance(rules, list):
        rules = []

    found = False
    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") == SMB_DENY_WALKTHROUGH_RULE_ID:
            rule["enabled"] = not paid
            found = True
            break

    if not found and not paid:
        rules.append(
            {
                "id": SMB_DENY_WALKTHROUGH_RULE_ID,
                "name": "Free tier blocks guided walkthrough",
                "cel": "tool_call.tool_name == 'walkthrough'",
                "action": "block",
                "enabled": True,
            }
        )

    raw["tool_rules"] = rules
    dest.write_text(yaml.dump(raw, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return dest


def reload_policy_engine(*, client: httpx.Client | None = None) -> None:
    """Ask policy-engine to reload tenant overrides from disk."""
    url = config.settings.policy_engine_url.rstrip("/") + "/v1/reload"
    headers: dict[str, str] = {}
    if config.settings.internal_token:
        headers["Authorization"] = f"Bearer {config.settings.internal_token}"

    own_client = client is None
    http = client or httpx.Client(timeout=10.0)
    try:
        resp = http.post(url, headers=headers)
    finally:
        if own_client:
            http.close()

    if resp.status_code >= 400:
        raise PolicyEngineError(
            f"policy-engine reload HTTP {resp.status_code}: {resp.text[:500]}"
        )
