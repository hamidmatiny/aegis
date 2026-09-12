"""Run a single task through harness run_agent() with a scoped ToolRegistry."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import httpx

from aegis_corp_orchestrator.config import settings
from aegis_corp_orchestrator.db.connection import get_pool
from aegis_corp_orchestrator.runner.mock_model import ScriptedToolModelClient, script_for_department
from aegis_corp_orchestrator.tools.catalog import build_registry
from aegis_harness.clients import AgentGateClient, ModelRouterClient
from aegis_harness.loop import run_agent

logger = logging.getLogger(__name__)


def _request_audit_receipt(metadata: dict[str, Any]) -> str | None:
    if not settings.audit_service_url or not settings.internal_token:
        return None
    url = settings.audit_service_url.rstrip("/") + "/v1/receipts"
    headers = {
        "Authorization": f"Bearer {settings.internal_token}",
        "Content-Type": "application/json",
    }
    body = {
        "event_type": "TOOL_GATE",
        "tenant_id": "corp-orchestrator",
        "metadata": metadata,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            logger.warning("audit receipt failed: %s %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        return str(data.get("receipt_id") or "") or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit receipt error: %s", exc)
        return None


async def execute_task(task_id: UUID) -> dict[str, Any]:
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT t.task_id, t.agent_id, t.input, t.status,
                   a.role, a.model_provider, a.model_name, a.context_scope,
                   a.department, a.team
            FROM tasks t
            JOIN agents a ON a.agent_id = t.agent_id
            WHERE t.task_id = %s
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        return {"error": "task_not_found", "task_id": str(task_id)}

    (
        _tid,
        agent_id,
        task_input,
        _status,
        role,
        model_provider,
        model_name,
        context_scope,
        department,
        team,
    ) = row
    scope = context_scope if isinstance(context_scope, dict) else json.loads(context_scope or "{}")
    allowed = list(scope.get("allowed_tools") or [])

    with pool.connection() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'running' WHERE task_id = %s",
            (task_id,),
        )
        conn.execute(
            "UPDATE agents SET status = 'running', updated_at = now() WHERE agent_id = %s",
            (agent_id,),
        )

    registry = build_registry(allowed)
    provider = "mock" if settings.force_mock_llm else str(model_provider)
    model = "mock-model" if settings.force_mock_llm else str(model_name)

    gate_key = ""
    if settings.agent_gate_api_keys:
        gate_key = settings.agent_gate_api_keys.split(",")[0].strip()

    if settings.force_mock_llm:
        model_client: Any = ScriptedToolModelClient(
            script_for_department(
                str(department),
                str(team),
                settings.healthz_url,
                settings.github_actions_url,
            )
        )
    else:
        model_client = ModelRouterClient(
            base_url=settings.model_router_url,
            internal_token=settings.internal_token,
        )
    gate_client = AgentGateClient(
        base_url=settings.agent_gate_url,
        service_api_key=gate_key,
    )

    system_prompt = (
        f"You are an AEGIS corp agent.\n"
        f"Department: {department}\nTeam: {team}\nRole: {role}\n"
        f"Allowed tools: {', '.join(allowed) or '(none)'}\n"
        f"Denied data domains: {scope.get('denied_data_domains')}\n"
        f"Use only your tools. Cross-department work must use corp_escalate. "
        f"Never claim you performed actions you did not tool-call."
    )

    final_status = "done"
    result_text = ""
    try:
        # Short approval timeout so IRREVERSIBLE tools don't hang scheduled runs
        outcome = await run_agent(
            system_prompt=system_prompt,
            user_message=str(task_input),
            tools=registry,
            model_client=model_client,
            gate_client=gate_client,
            model=model,
            provider=provider,
            agent_id=str(agent_id),
            max_turns=6,
            approval_timeout_seconds=5.0,
            approval_poll_interval_seconds=1.0,
        )
        result_text = outcome.final_answer or json.dumps(
            {"transcript_turns": outcome.turns_used, "notes": "empty final_answer"},
        )
        # Detect escalation markers in transcript
        for turn in outcome.transcript:
            blob = json.dumps(turn, default=str)
            if "AWAITING_HUMAN_APPROVAL" in blob or "escalated_task_id" in blob:
                final_status = "escalated"
                break
    except Exception as exc:  # noqa: BLE001
        logger.exception("task %s failed", task_id)
        final_status = "failed"
        result_text = json.dumps({"error": str(exc)})

    receipt_id = _request_audit_receipt(
        {
            "source": "corp-orchestrator",
            "task_id": str(task_id),
            "agent_id": str(agent_id),
            "department": department,
            "team": team,
            "status": final_status,
        }
    )

    agent_status = "idle"
    if final_status == "escalated":
        agent_status = "escalated"
    elif final_status == "failed":
        agent_status = "error"

    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = %s, result = %s, audit_receipt_id = %s, completed_at = now()
            WHERE task_id = %s
            """,
            (final_status, result_text, receipt_id, task_id),
        )
        conn.execute(
            "UPDATE agents SET status = %s, updated_at = now() WHERE agent_id = %s",
            (agent_status, agent_id),
        )

    return {
        "task_id": str(task_id),
        "agent_id": str(agent_id),
        "status": final_status,
        "result": result_text[:2000],
        "audit_receipt_id": receipt_id,
        "provider": provider,
        "model": model,
    }


async def enqueue_and_run(agent_id: UUID, task_input: str) -> dict[str, Any]:
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO tasks (agent_id, input, status)
            VALUES (%s, %s, 'queued')
            RETURNING task_id
            """,
            (agent_id, task_input),
        ).fetchone()
    assert row is not None
    return await execute_task(row[0])
