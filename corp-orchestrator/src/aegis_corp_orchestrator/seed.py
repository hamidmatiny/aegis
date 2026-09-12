"""Seed the 12 department agents (idempotent upsert by department+team)."""

from __future__ import annotations

import json
import logging

from aegis_corp_orchestrator.db.connection import get_pool

logger = logging.getLogger(__name__)

# Default first-task prompts used by scheduler / manual run-all.
DEFAULT_TASKS: dict[tuple[str, str], str] = {
    ("website", "ui_ux_branding"): (
        "Audit brand color/asset consistency across smb-portal, dashboard, and "
        "deploy/oracle/demo-web. Use corp_read_repo_file on CSS/theme files. "
        "If you find mismatches, use corp_list_agents for department=website and "
        "corp_escalate to management_board with a concise report."
    ),
    ("website", "web_engineering"): (
        "Poll the configured healthz URL and the latest GitHub Actions run on main "
        "via corp_http_get. If health is not ok or CI conclusion is failure, "
        "corp_escalate to website management_board."
    ),
    ("website", "management_board"): (
        "Use corp_sql_readonly query_key=open_escalations_website and prioritize "
        "open website escalations. Read-only synthesis only — do not change the site."
    ),
    ("cybersecurity", "threat_intel"): (
        "Use corp_sql_readonly query_key=tracked_software and cve_count. Propose one "
        "relevant CVE addition via corp_propose_cve_write targeting management or "
        "defensive_eng reviewer — never call corp_apply_cve_write."
    ),
    ("cybersecurity", "defensive_eng"): (
        "Draft a policy-rule suggestion for policy-engine/policies/default.yaml based "
        "on common prompt-injection patterns. Do not write files; return the draft "
        "suggestion in your final answer."
    ),
    ("cybersecurity", "red_team"): (
        "Run corp_redteam_run with a classic injection canary and summarize whether "
        "input-defense blocked or allowed it. File findings in your final answer."
    ),
    ("finance", "pnl_analyst"): (
        "Produce a daily P&L-style summary using corp_sql_readonly keys usage_today, "
        "stripe_customers, and tenant_tiers. You have no payment-moving tools."
    ),
    ("hr", "agent_ops"): (
        "Use corp_sql_readonly query_key=agent_ops and report error rates, stuck tasks, "
        "and agents that look overdue."
    ),
    ("engineering", "core_infra"): (
        "Run corp_infra_health and escalate to hr agent_ops if postgres or redis is unhealthy."
    ),
    ("data", "quality"): (
        "Run corp_sql_readonly for usage_nulls, cve_count, and cve_dupes. Flag nulls, "
        "duplicates, or empty CVE tables."
    ),
    ("trust", "safety_privacy"): (
        "Use corp_audit_receipts to review recent receipts for policy-violation trends "
        "and PII-related signals. Summarize only — no external disclosure."
    ),
    ("sales", "growth"): (
        "Use corp_sql_readonly signup_counts and tenant_tiers, then corp_draft_outreach "
        "with a short draft. Never call corp_publish_outreach."
    ),
}


def _scope(*tools: str, denied: list[str] | None = None) -> dict:
    return {
        "allowed_tools": list(tools),
        "denied_data_domains": denied or [],
    }


AGENTS: list[dict] = [
    {
        "department": "website",
        "team": "ui_ux_branding",
        "role": "UI/UX & Branding auditor for portal/dashboard/demo-web consistency",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 */6 * * *",
        "escalation_target": "website/management_board",
        "context_scope": _scope(
            "corp_read_repo_file",
            "corp_escalate",
            "corp_list_agents",
        ),
    },
    {
        "department": "website",
        "team": "web_engineering",
        "role": "Web Engineering — healthz and CI monitor",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 * * * *",
        "escalation_target": "website/management_board",
        "context_scope": _scope(
            "corp_http_get",
            "corp_escalate",
            "corp_list_agents",
        ),
    },
    {
        "department": "website",
        "team": "management_board",
        "role": "Website Management Board — prioritizes website escalations (read-only)",
        "model_provider": "grok",
        "model_name": "grok-4",
        "schedule": "0 */6 * * *",
        "escalation_target": "hr/agent_ops",
        "context_scope": _scope("corp_sql_readonly", "corp_list_agents"),
    },
    {
        "department": "cybersecurity",
        "team": "threat_intel",
        "role": "Threat Intelligence — CVE relevance research (propose only)",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 */12 * * *",
        "escalation_target": "cybersecurity/defensive_eng",
        "context_scope": _scope(
            "corp_sql_readonly",
            "corp_propose_cve_write",
            "corp_list_agents",
            "corp_escalate",
        ),
    },
    {
        "department": "cybersecurity",
        "team": "defensive_eng",
        "role": "Defensive Engineering — draft policy suggestions",
        "model_provider": "grok",
        "model_name": "grok-4",
        "schedule": "0 */12 * * *",
        "escalation_target": "cybersecurity/threat_intel",
        "context_scope": _scope("corp_sql_readonly", "corp_list_agents"),
    },
    {
        "department": "cybersecurity",
        "team": "red_team",
        "role": "Red Team — runs existing redteam probes on schedule",
        "model_provider": "grok",
        "model_name": "grok-4",
        "schedule": "0 0 * * *",
        "escalation_target": "cybersecurity/defensive_eng",
        "context_scope": _scope(
            "corp_redteam_run",
            "corp_escalate",
            "corp_list_agents",
        ),
    },
    {
        "department": "finance",
        "team": "pnl_analyst",
        "role": "Finance P&L analyst — token cost + Stripe revenue read-only",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 6 * * *",
        "escalation_target": "hr/agent_ops",
        "context_scope": _scope("corp_sql_readonly"),  # zero Stripe write tools
    },
    {
        "department": "hr",
        "team": "agent_ops",
        "role": "HR / agent ops — meta-monitor agents and tasks",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 * * * *",
        "escalation_target": "engineering/core_infra",
        "context_scope": _scope("corp_sql_readonly", "corp_list_agents", "corp_escalate"),
    },
    {
        "department": "engineering",
        "team": "core_infra",
        "role": "Core infra — Docker/Postgres/Redis/backup health",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 * * * *",
        "escalation_target": "hr/agent_ops",
        "context_scope": _scope(
            "corp_infra_health",
            "corp_escalate",
            "corp_list_agents",
        ),
    },
    {
        "department": "data",
        "team": "quality",
        "role": "Data quality — CVE and usage_events checks",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 */6 * * *",
        "escalation_target": "engineering/core_infra",
        "context_scope": _scope("corp_sql_readonly", "corp_escalate", "corp_list_agents"),
    },
    {
        "department": "trust",
        "team": "safety_privacy",
        "role": "Trust/Safety/Privacy — audit receipt trend review",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 */12 * * *",
        "escalation_target": "cybersecurity/defensive_eng",
        "context_scope": _scope("corp_audit_receipts", "corp_sql_readonly"),
    },
    {
        "department": "sales",
        "team": "growth",
        "role": "Sales & Marketing — metrics + draft outreach (never publish)",
        "model_provider": "grok",
        "model_name": "grok-4-fast",
        "schedule": "0 8 * * *",
        "escalation_target": "website/management_board",
        "context_scope": _scope(
            "corp_sql_readonly",
            "corp_draft_outreach",
            # corp_publish_outreach intentionally omitted
        ),
    },
]


def seed_agents() -> int:
    pool = get_pool()
    count = 0
    with pool.connection() as conn:
        for a in AGENTS:
            conn.execute(
                """
                INSERT INTO agents (
                    department, team, role, model_provider, model_name,
                    context_scope, schedule, escalation_target, status
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, 'idle')
                ON CONFLICT (department, team) DO UPDATE SET
                    role = EXCLUDED.role,
                    model_provider = EXCLUDED.model_provider,
                    model_name = EXCLUDED.model_name,
                    context_scope = EXCLUDED.context_scope,
                    schedule = EXCLUDED.schedule,
                    escalation_target = EXCLUDED.escalation_target,
                    updated_at = now()
                """,
                (
                    a["department"],
                    a["team"],
                    a["role"],
                    a["model_provider"],
                    a["model_name"],
                    json.dumps(a["context_scope"]),
                    a["schedule"],
                    a["escalation_target"],
                ),
            )
            count += 1
    logger.info("seeded %s agents", count)
    return count
