"""Conservative cron scheduler — ticks once per minute, no tight loops."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from croniter import croniter

from aegis_corp_orchestrator.config import settings
from aegis_corp_orchestrator.db.connection import get_pool
from aegis_corp_orchestrator.runner.execute import enqueue_and_run
from aegis_corp_orchestrator.seed import DEFAULT_TASKS

logger = logging.getLogger(__name__)

_last_fire: dict[str, datetime] = {}


def _due(schedule: str, agent_key: str, now: datetime) -> bool:
    try:
        base = _last_fire.get(agent_key) or now.replace(second=0, microsecond=0)
        itr = croniter(schedule, base)
        nxt = itr.get_next(datetime)
        # croniter returns naive or aware depending on input; normalize
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now_cmp = now.replace(tzinfo=timezone.utc)
        else:
            now_cmp = now
        # Fire if next scheduled time is at or before now and we haven't fired this minute
        if nxt <= now_cmp:
            minute_key = now_cmp.replace(second=0, microsecond=0)
            prev = _last_fire.get(agent_key)
            if prev and prev >= minute_key:
                return False
            return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("bad schedule %s: %s", schedule, exc)
    return False


async def scheduler_loop(stop: asyncio.Event) -> None:
    if not settings.scheduler_enabled:
        logger.info("corp scheduler disabled")
        return
    logger.info("corp scheduler started (60s tick)")
    while not stop.is_set():
        try:
            now = datetime.now(timezone.utc)
            pool = get_pool()
            with pool.connection() as conn:
                agents = conn.execute(
                    "SELECT agent_id, department, team, schedule, status FROM agents"
                ).fetchall()
            for agent_id, department, team, schedule, status in agents:
                if status == "running":
                    continue
                key = f"{department}/{team}"
                if not _due(str(schedule), key, now):
                    continue
                # Skip if already has queued/running task
                with pool.connection() as conn:
                    busy = conn.execute(
                        """
                        SELECT 1 FROM tasks
                        WHERE agent_id = %s AND status IN ('queued', 'running')
                        LIMIT 1
                        """,
                        (agent_id,),
                    ).fetchone()
                if busy:
                    continue
                prompt = DEFAULT_TASKS.get((department, team), "Run your standard health check.")
                _last_fire[key] = now.replace(second=0, microsecond=0)
                logger.info("scheduler firing %s", key)
                try:
                    await enqueue_and_run(agent_id, prompt)
                except Exception:  # noqa: BLE001
                    logger.exception("scheduler run failed for %s", key)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=60.0)
        except TimeoutError:
            continue
