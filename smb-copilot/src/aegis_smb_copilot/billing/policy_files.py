"""Write per-tenant policy-engine override YAML (free tier by default)."""

from __future__ import annotations

from pathlib import Path

from aegis_smb_copilot import config

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
