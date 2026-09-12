"""Deferred human approval for parked corp tool calls."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import httpx

from aegis_corp_orchestrator.config import settings
from aegis_corp_orchestrator.db.connection import get_pool
from aegis_corp_orchestrator.tools.catalog import get_tool
from aegis_harness.clients import GateDecision
from aegis_harness.loop import _execute_after_gate

logger = logging.getLogger(__name__)


def _gate_headers(service: bool = True) -> dict[str, str]:
    if service:
        key = (settings.agent_gate_api_keys or "").split(",")[0].strip()
    else:
        key = (settings.agent_gate_reviewer_keys or "").split(",")[0].strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def _evaluate_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    agent_id: str,
    risk_level: str,
) -> dict[str, Any]:
    payload = {
        "tenant_id": "default",
        "mode": "enforce",
        "tool_call": {
            "tool_name": tool_name,
            "agent_id": agent_id,
            "risk_level": risk_level,
            "arguments": [{"name": k, "value": v} for k, v in arguments.items()],
        },
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{settings.agent_gate_url.rstrip('/')}/v1/evaluate",
            headers={**_gate_headers(True), "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


def _decide(approval_id: str, *, approved: bool, comment: str) -> dict[str, Any]:
    body = {
        "approval_id": approval_id,
        "approved": approved,
        "reviewer_id": "corp-bev-admin",
        "comment": comment or ("approved via corp BEV" if approved else "denied via corp BEV"),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{settings.agent_gate_url.rstrip('/')}/v1/approvals/{approval_id}/decide",
            headers={**_gate_headers(False), "Content-Type": "application/json"},
            json=body,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"decide failed: {resp.status_code} {resp.text[:400]}")
        return resp.json()


def _approval_still_pending(approval_id: str) -> bool:
    if not approval_id:
        return False
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{settings.agent_gate_url.rstrip('/')}/v1/approvals/{approval_id}",
            headers=_gate_headers(True),
        )
    if resp.status_code != 200:
        return False
    data = resp.json()
    return data.get("status") == "AWAITING_HUMAN_APPROVAL"


def decide_pending_task(
    task_id: UUID,
    *,
    approved: bool,
    comment: str = "",
) -> dict[str, Any]:
    """Approve or deny a parked pending tool call; on approve, execute the tool."""
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT t.task_id, t.agent_id, t.status, t.pending_approval, t.result,
                   a.department, a.team
            FROM tasks t
            JOIN agents a ON a.agent_id = t.agent_id
            WHERE t.task_id = %s
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        return {"error": "task_not_found", "task_id": str(task_id)}
    _tid, agent_id, status, pending_raw, _prev_result, department, team = row
    if status != "escalated" or not pending_raw:
        return {
            "error": "no_pending_approval",
            "task_id": str(task_id),
            "status": status,
        }
    pending = pending_raw if isinstance(pending_raw, dict) else json.loads(pending_raw)
    tool_name = str(pending.get("tool_name") or "")
    arguments = pending.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}
    risk_level = str(pending.get("risk_level") or "")
    approval_id = str(pending.get("approval_request_id") or "")

    # Prefer deciding the live approval; if expired/gone, re-evaluate then decide.
    used_approval_id = approval_id
    reissued = False
    if not _approval_still_pending(approval_id):
        eval_resp = _evaluate_tool(
            tool_name=tool_name,
            arguments=arguments,
            agent_id=str(agent_id),
            risk_level=risk_level,
        )
        decision = eval_resp.get("decision") or {}
        new_id = decision.get("approval_request_id") or ""
        status_now = decision.get("status") or ""
        if status_now == "APPROVED":
            # Unusual — policy no longer requires approval; treat as allowed.
            used_approval_id = new_id or approval_id
        elif status_now != "AWAITING_HUMAN_APPROVAL" or not new_id:
            return {
                "error": "re_evaluate_failed",
                "task_id": str(task_id),
                "decision": decision,
            }
        else:
            used_approval_id = new_id
            reissued = True

    decide_resp = _decide(used_approval_id, approved=approved, comment=comment)
    decide_status = (
        (decide_resp.get("decision") or {}).get("status")
        or decide_resp.get("status")
        or ""
    )

    if not approved:
        result = {
            "denied": True,
            "tool_name": tool_name,
            "approval_request_id": used_approval_id,
            "reissued": reissued,
            "comment": comment,
        }
        with pool.connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'failed',
                    result = %s,
                    pending_approval = NULL,
                    completed_at = now()
                WHERE task_id = %s
                """,
                (json.dumps(result), task_id),
            )
            conn.execute(
                "UPDATE agents SET status = 'idle', updated_at = now() WHERE agent_id = %s",
                (agent_id,),
            )
        return {"task_id": str(task_id), "status": "failed", "result": result}

    tool = get_tool(tool_name)
    if tool is None:
        return {"error": "unknown_tool", "tool_name": tool_name}

    gate_decision = GateDecision(
        status="APPROVED",
        approval_request_id=used_approval_id,
        raw=decide_resp,
    )
    try:
        tool_result = _execute_after_gate(tool, arguments, gate_decision)
    except Exception as exc:  # noqa: BLE001
        logger.exception("post-approval execute failed for %s", task_id)
        err = {"error": str(exc), "tool_name": tool_name, "approved_but_failed": True}
        with pool.connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'failed', result = %s, pending_approval = NULL, completed_at = now()
                WHERE task_id = %s
                """,
                (json.dumps(err), task_id),
            )
            conn.execute(
                "UPDATE agents SET status = 'error', updated_at = now() WHERE agent_id = %s",
                (agent_id,),
            )
        return {"task_id": str(task_id), "status": "failed", "result": err}

    result = {
        "approved": True,
        "tool_name": tool_name,
        "approval_request_id": used_approval_id,
        "reissued": reissued,
        "decide_status": decide_status,
        "tool_result": tool_result,
        "department": department,
        "team": team,
    }
    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'done',
                result = %s,
                pending_approval = NULL,
                completed_at = now()
            WHERE task_id = %s
            """,
            (json.dumps(result), task_id),
        )
        conn.execute(
            "UPDATE agents SET status = 'idle', updated_at = now() WHERE agent_id = %s",
            (agent_id,),
        )
    return {"task_id": str(task_id), "status": "done", "result": result}
