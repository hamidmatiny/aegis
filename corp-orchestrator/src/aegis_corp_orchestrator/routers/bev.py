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
                SELECT task_id, input, status, result, pending_approval,
                       created_at, completed_at
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
                    "pending_approval": recent[4],
                    "created_at": recent[5].isoformat() if recent[5] else None,
                    "completed_at": recent[6].isoformat() if recent[6] else None,
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


@router.get("/trajectory")
def bev_trajectory(_admin: Any = Depends(require_admin)) -> dict[str, Any]:
    """CEO latest Trajectory Report + sparse signup history for charting."""
    pool = get_pool()
    with pool.connection() as conn:
        ceo = conn.execute(
            """
            SELECT agent_id, status, model_provider, model_name, schedule, context_scope
            FROM agents WHERE department = 'executive' AND team = 'ceo'
            """
        ).fetchone()
        if ceo is None:
            return {
                "ceo_registered": False,
                "report": None,
                "signup_history_14d": [],
                "chart": {"status": "not_enough_data_yet", "points": []},
            }
        task = conn.execute(
            """
            SELECT task_id, status, result, created_at, completed_at
            FROM tasks WHERE agent_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (ceo[0],),
        ).fetchone()
        history: list[dict[str, Any]] = []
        try:
            rows = conn.execute(
                """
                SELECT date_trunc('day', created_at)::date AS day, count(*) AS signups
                FROM tenants
                WHERE created_at >= now() - interval '14 days'
                GROUP BY 1 ORDER BY 1
                """
            ).fetchall()
            history = [
                {"day": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]), "signups": r[1]}
                for r in rows
            ]
        except Exception:  # noqa: BLE001
            history = []

    report = None
    if task:
        report = {
            "task_id": str(task[0]),
            "status": task[1],
            "result": task[2],
            "created_at": task[3].isoformat() if task[3] else None,
            "completed_at": task[4].isoformat() if task[4] else None,
        }

    chart_status = "ok" if len(history) >= 2 else "not_enough_data_yet"
    scope = ceo[5] if isinstance(ceo[5], dict) else {}
    return {
        "ceo_registered": True,
        "agent_id": str(ceo[0]),
        "agent_status": ceo[1],
        "model_provider": ceo[2],
        "model_name": ceo[3],
        "schedule": ceo[4],
        "allowed_tools": list((scope or {}).get("allowed_tools") or []),
        "report": report,
        "signup_history_14d": history,
        "chart": {"status": chart_status, "points": history, "metric": "signups"},
    }
