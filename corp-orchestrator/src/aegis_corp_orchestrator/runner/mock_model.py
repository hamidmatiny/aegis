"""Deterministic model client that drives real gated tool calls under mock LLM.

When CORP_FORCE_MOCK_LLM is on, model-router's mock echo would never emit
tool_call JSON — so tools would never run. This client walks a short
script of tool calls (still executed only via harness → agent-gate), then
returns a final answer summarizing tool results from the message history.
"""

from __future__ import annotations

import json
from typing import Any


class ScriptedToolModelClient:
    """Implements ModelClient protocol with a fixed tool-call script."""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        # Each item: {"tool_name": str, "arguments": dict}
        self._script = list(script)
        self._i = 0

    async def complete(
        self, *, model: str, messages: list[dict[str, str]], provider: str = ""
    ) -> str:
        if self._i < len(self._script):
            step = self._script[self._i]
            self._i += 1
            return json.dumps(
                {
                    "tool_call": {
                        "tool_name": step["tool_name"],
                        "arguments": step.get("arguments") or {},
                    }
                }
            )
        # Final answer: concatenate recent tool results from history
        snippets: list[str] = []
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content", "").startswith("TOOL_RESULT"):
                snippets.append(msg["content"][:1500])
            elif msg.get("role") == "user" and "tool" in msg.get("content", "").lower():
                snippets.append(msg["content"][:1500])
        # harness feeds tool results as user messages — capture last few
        for msg in messages[-6:]:
            content = msg.get("content") or ""
            if content and msg.get("role") != "system":
                if '"tool_call"' not in content:
                    snippets.append(content[:1200])
        body = "\n---\n".join(snippets[-4:]) if snippets else "(no tool results)"
        return f"Mock-corp run complete.\n\n{body}"


def script_for_department(department: str, team: str, healthz_url: str, gh_url: str) -> list[dict[str, Any]]:
    """Return a minimal tool script matching each team's first task."""
    key = (department, team)
    scripts: dict[tuple[str, str], list[dict[str, Any]]] = {
        ("website", "ui_ux_branding"): [
            {
                "tool_name": "corp_read_repo_file",
                "arguments": {"path": "smb-portal/src/styles.css"},
            },
            {
                "tool_name": "corp_read_repo_file",
                "arguments": {"path": "dashboard/src/styles.css"},
            },
            {
                "tool_name": "corp_read_repo_file",
                "arguments": {"path": "deploy/oracle/demo-web/index.html"},
            },
        ],
        ("website", "web_engineering"): [
            {"tool_name": "corp_http_get", "arguments": {"url": healthz_url}},
            {"tool_name": "corp_http_get", "arguments": {"url": gh_url}},
        ],
        ("website", "management_board"): [
            {
                "tool_name": "corp_sql_readonly",
                "arguments": {"query_key": "open_escalations_website"},
            },
        ],
        ("cybersecurity", "threat_intel"): [
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "tracked_software"}},
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "cve_count"}},
            {"tool_name": "corp_list_agents", "arguments": {"department": "cybersecurity"}},
        ],
        ("cybersecurity", "defensive_eng"): [
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "cve_count"}},
        ],
        ("cybersecurity", "red_team"): [
            {"tool_name": "corp_redteam_run", "arguments": {}},
        ],
        ("finance", "pnl_analyst"): [
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "usage_today"}},
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "stripe_customers"}},
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "tenant_tiers"}},
        ],
        ("hr", "agent_ops"): [
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "agent_ops"}},
        ],
        ("engineering", "core_infra"): [
            {"tool_name": "corp_infra_health", "arguments": {}},
        ],
        ("data", "quality"): [
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "usage_nulls"}},
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "cve_dupes"}},
        ],
        ("trust", "safety_privacy"): [
            {"tool_name": "corp_audit_receipts", "arguments": {"limit": 5}},
        ],
        ("sales", "growth"): [
            {"tool_name": "corp_sql_readonly", "arguments": {"query_key": "signup_counts"}},
            {
                "tool_name": "corp_draft_outreach",
                "arguments": {
                    "subject": "AEGIS for SMB — weekly note",
                    "body": "Draft only: invite to try defenseaegis.org (human must approve publish).",
                    "channel": "email",
                },
            },
        ],
        ("executive", "ceo"): [
            {"tool_name": "corp_read_company_state", "arguments": {}},
        ],
    }
    return scripts.get(key, [{"tool_name": "corp_list_agents", "arguments": {}}])
