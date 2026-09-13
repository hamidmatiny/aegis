"""Agent and task HTTP routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from aegis_corp_orchestrator.auth.session import require_admin, require_read_or_admin
from aegis_corp_orchestrator.db.connection import get_pool
from aegis_corp_orchestrator.runner.approve import decide_pending_task
from aegis_corp_orchestrator.runner.execute import enqueue_and_run, execute_task
from aegis_corp_orchestrator.seed import DEFAULT_TASKS
from fastapi import Depends

router = APIRouter(prefix="/v1", tags=["corp"])


class RunTaskBody(BaseModel):
    agent_id: UUID | None = None
    department: str | None = None
    team: str | None = None
    input: str | None = None


class DecideBody(BaseModel):
    approved: bool
    comment: str = Field(default="")


class ParkPendingBody(BaseModel):
    """Ops/demo: create an escalated task with a parked pending tool call."""

    department: str
    team: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = ""
    approval_request_id: str | None = None
    input: str = "Parked pending tool call for human review"


@router.get("/agents")
def list_agents(_admin: Any = Depends(require_read_or_admin)) -> dict[str, Any]:
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT agent_id, department, team, role, model_provider, model_name,
                   context_scope, status, schedule, escalation_target,
                   created_at, updated_at
            FROM agents ORDER BY department, team
            """
        ).fetchall()
    agents = []
    for r in rows:
        agents.append(
            {
                "agent_id": str(r[0]),
                "department": r[1],
                "team": r[2],
                "role": r[3],
                "model_provider": r[4],
                "model_name": r[5],
                "context_scope": r[6],
                "status": r[7],
                "schedule": r[8],
                "escalation_target": r[9],
                "created_at": r[10].isoformat() if r[10] else None,
                "updated_at": r[11].isoformat() if r[11] else None,
            }
        )
    return {"agents": agents, "count": len(agents)}


@router.get("/tasks")
def list_tasks(
    limit: int = 50,
    agent_id: UUID | None = None,
    _admin: Any = Depends(require_read_or_admin),
) -> dict[str, Any]:
    pool = get_pool()
    with pool.connection() as conn:
        if agent_id:
            rows = conn.execute(
                """
                SELECT task_id, agent_id, input, status, result, audit_receipt_id,
                       pending_approval, created_at, completed_at
                FROM tasks WHERE agent_id = %s
                ORDER BY created_at DESC LIMIT %s
                """,
                (agent_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT task_id, agent_id, input, status, result, audit_receipt_id,
                       pending_approval, created_at, completed_at
                FROM tasks ORDER BY created_at DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
    tasks = []
    for r in rows:
        tasks.append(
            {
                "task_id": str(r[0]),
                "agent_id": str(r[1]),
                "input": r[2],
                "status": r[3],
                "result": r[4],
                "audit_receipt_id": r[5],
                "pending_approval": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
                "completed_at": r[8].isoformat() if r[8] else None,
            }
        )
    return {"tasks": tasks}


@router.post("/tasks/run")
async def run_task(
    body: RunTaskBody,
    _admin: Any = Depends(require_admin),
) -> dict[str, Any]:
    pool = get_pool()
    agent_id = body.agent_id
    if agent_id is None:
        if not body.department or not body.team:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "missing_agent", "message": "agent_id or department+team required"},
            )
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT agent_id FROM agents WHERE department = %s AND team = %s",
                (body.department, body.team),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"type": "agent_not_found"})
        agent_id = row[0]

    with pool.connection() as conn:
        meta = conn.execute(
            "SELECT department, team FROM agents WHERE agent_id = %s",
            (agent_id,),
        ).fetchone()
    if meta is None:
        raise HTTPException(status_code=404, detail={"type": "agent_not_found"})
    prompt = body.input or DEFAULT_TASKS.get((meta[0], meta[1]), "Run your standard check.")
    return await enqueue_and_run(agent_id, prompt)


@router.post("/tasks/{task_id}/run")
async def rerun_task(
    task_id: UUID,
    _admin: Any = Depends(require_admin),
) -> dict[str, Any]:
    return await execute_task(task_id)


@router.post("/tasks/{task_id}/decide")
def decide_task(
    task_id: UUID,
    body: DecideBody,
    _admin: Any = Depends(require_admin),
) -> dict[str, Any]:
    """Approve/deny a parked pending tool call (deferred human review)."""
    out = decide_pending_task(task_id, approved=body.approved, comment=body.comment)
    if out.get("error"):
        raise HTTPException(status_code=400, detail=out)
    return out


@router.post("/tasks/park-pending")
def park_pending(
    body: ParkPendingBody,
    _admin: Any = Depends(require_admin),
) -> dict[str, Any]:
    """Create an escalated task with pending_approval (for deferred-approve demos)."""
    import json as _json
    from datetime import datetime, timezone

    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT agent_id FROM agents WHERE department = %s AND team = %s",
            (body.department, body.team),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"type": "agent_not_found"})
        agent_id = row[0]
        approval_id = body.approval_request_id
        if not approval_id:
            # Fresh evaluate so agent-gate holds a live approval id.
            from aegis_corp_orchestrator.runner.approve import _evaluate_tool

            ev = _evaluate_tool(
                tool_name=body.tool_name,
                arguments=body.arguments,
                agent_id=str(agent_id),
                risk_level=body.risk_level,
            )
            decision = ev.get("decision") or {}
            approval_id = decision.get("approval_request_id")
            if (decision.get("status") or "") != "AWAITING_HUMAN_APPROVAL" or not approval_id:
                raise HTTPException(
                    status_code=400,
                    detail={"type": "evaluate_did_not_escalate", "decision": decision},
                )
        pending = {
            "tool_name": body.tool_name,
            "arguments": body.arguments,
            "approval_request_id": approval_id,
            "risk_level": body.risk_level,
            "parked_at": datetime.now(timezone.utc).isoformat(),
        }
        task_row = conn.execute(
            """
            INSERT INTO tasks (agent_id, input, status, result, pending_approval)
            VALUES (%s, %s, 'escalated', %s, %s::jsonb)
            RETURNING task_id
            """,
            (
                agent_id,
                body.input,
                _json.dumps({"status": "escalated", "pending_approval": pending}),
                _json.dumps(pending),
            ),
        ).fetchone()
        conn.execute(
            "UPDATE agents SET status = 'escalated', updated_at = now() WHERE agent_id = %s",
            (agent_id,),
        )
    return {
        "task_id": str(task_row[0]),
        "agent_id": str(agent_id),
        "status": "escalated",
        "pending_approval": pending,
    }


@router.get("/tasks/pending")
def list_pending(_admin: Any = Depends(require_read_or_admin)) -> dict[str, Any]:
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT t.task_id, t.agent_id, a.department, a.team, t.pending_approval,
                   t.result, t.created_at
            FROM tasks t
            JOIN agents a ON a.agent_id = t.agent_id
            WHERE t.status = 'escalated' AND t.pending_approval IS NOT NULL
            ORDER BY t.created_at DESC
            """
        ).fetchall()
    return {
        "pending": [
            {
                "task_id": str(r[0]),
                "agent_id": str(r[1]),
                "department": r[2],
                "team": r[3],
                "pending_approval": r[4],
                "result": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]
    }


@router.post("/tasks/run-all-departments")
async def run_all_departments(_admin: Any = Depends(require_admin)) -> dict[str, Any]:
    """Enqueue+run one default task per department (first agent of each)."""
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (department) agent_id, department, team
            FROM agents ORDER BY department, team
            """
        ).fetchall()
    results = []
    for agent_id, department, team in rows:
        prompt = DEFAULT_TASKS.get((department, team), "Run your standard check.")
        results.append(await enqueue_and_run(agent_id, prompt))
    return {"results": results, "count": len(results)}


@router.post("/tasks/run-all-agents")
async def run_all_agents(_admin: Any = Depends(require_admin)) -> dict[str, Any]:
    """Enqueue+run one default task for each of the 12 agents."""
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT agent_id, department, team FROM agents ORDER BY department, team"
        ).fetchall()
    results = []
    for agent_id, department, team in rows:
        prompt = DEFAULT_TASKS.get((department, team), "Run your standard check.")
        results.append(await enqueue_and_run(agent_id, prompt))
    return {"results": results, "count": len(results)}
