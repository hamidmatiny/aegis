"""Bird's Eye View APIs — live DB counts only, never fabricated."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from aegis_corp_orchestrator.auth.session import require_admin
from aegis_corp_orchestrator.db.connection import get_pool

router = APIRouter(prefix="/v1/bev", tags=["bev"])


@router.get("/summary")
def bev_summary(_admin: Any = Depends(require_admin)) -> dict[str, Any]:
    pool = get_pool()
    with pool.connection() as conn:
        total = conn.execute("SELECT count(*) FROM agents").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, count(*) FROM agents GROUP BY status"
        ).fetchall()
        tasks_today = conn.execute(
            """
            SELECT count(*) FROM tasks
            WHERE status = 'done' AND completed_at >= date_trunc('day', now())
            """
        ).fetchone()[0]
        escalations_open = conn.execute(
            """
            SELECT count(*) FROM tasks WHERE status IN ('queued', 'escalated')
            AND (
              input ILIKE '%escalate%' OR status = 'escalated'
              OR EXISTS (
                SELECT 1 FROM agents a WHERE a.agent_id = tasks.agent_id
                AND a.status = 'escalated'
              )
            )
            """
        ).fetchone()[0]
        # Simpler open escalations: tasks with status escalated + agents escalated
        esc_tasks = conn.execute(
            "SELECT count(*) FROM tasks WHERE status = 'escalated'"
        ).fetchone()[0]
        esc_agents = conn.execute(
            "SELECT count(*) FROM agents WHERE status = 'escalated'"
        ).fetchone()[0]
        depts = conn.execute(
            "SELECT department, count(*) FROM agents GROUP BY department ORDER BY 1"
        ).fetchall()

    status_map = {s: c for s, c in by_status}
    return {
        "total_agents": total,
        "by_status": {
            "idle": status_map.get("idle", 0),
            "running": status_map.get("running", 0),
            "escalated": status_map.get("escalated", 0),
            "error": status_map.get("error", 0),
        },
        "tasks_completed_today": tasks_today,
        "escalations_open": esc_tasks + esc_agents,
        "departments": [{"department": d, "agent_count": c} for d, c in depts],
    }


@router.get("/departments/{department}")
def bev_department(department: str, _admin: Any = Depends(require_admin)) -> dict[str, Any]:
    pool = get_pool()
    with pool.connection() as conn:
        agents = conn.execute(
            """
            SELECT agent_id, team, role, status, model_provider, model_name, schedule
            FROM agents WHERE department = %s ORDER BY team
            """,
            (department,),
        ).fetchall()
        if not agents:
            raise HTTPException(status_code=404, detail={"type": "department_not_found"})
        out_agents = []
        for a in agents:
            recent = conn.execute(
                """
                SELECT task_id, input, status, result, created_at, completed_at
                FROM tasks WHERE agent_id = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (a[0],),
            ).fetchone()
            recent_task = None
            if recent:
                recent_task = {
                    "task_id": str(recent[0]),
                    "input": recent[1],
                    "status": recent[2],
                    "result": recent[3],
                    "created_at": recent[4].isoformat() if recent[4] else None,
                    "completed_at": recent[5].isoformat() if recent[5] else None,
                }
            out_agents.append(
                {
                    "agent_id": str(a[0]),
                    "team": a[1],
                    "role": a[2],
                    "status": a[3],
                    "model_provider": a[4],
                    "model_name": a[5],
                    "schedule": a[6],
                    "most_recent_task": recent_task,
                }
            )
    return {"department": department, "agents": out_agents}
