"""Funnel-stage event emit + aggregates (Growth conversion baseline)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from aegis_smb_copilot.db.connection import get_pool

logger = logging.getLogger(__name__)

# Canonical stage names — keep stable for Growth dashboards.
FUNNEL_EVENTS = frozenset(
    {
        "pageview",
        "signup_started",
        "signup_completed",
        "inventory_saved",
        "qa_asked",
        "cve_match_shown",
        "walkthrough_viewed",
        "upgrade_viewed",
        "upgrade_started",
        "upgrade_completed",
    }
)

# Ordered funnel for conversion math (subset of FUNNEL_EVENTS).
FUNNEL_STAGES: tuple[str, ...] = (
    "signup_started",
    "signup_completed",
    "inventory_saved",
    "qa_asked",
    "cve_match_shown",
    "walkthrough_viewed",
    "upgrade_viewed",
    "upgrade_started",
    "upgrade_completed",
)


def emit_funnel_event(
    event: str,
    *,
    path: str = "",
    session_id: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    """Best-effort insert; never raise into product request paths."""
    name = (event or "").strip().lower()
    if name not in FUNNEL_EVENTS:
        logger.warning("unknown funnel event %r — skipped", event)
        return
    try:
        pool = get_pool()
        with pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO smb_funnel_events (event, path, session_id, meta)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (
                    name,
                    (path or "")[:512],
                    (session_id or "")[:64],
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
    except Exception:
        logger.exception("failed to emit funnel event %s", name)


def funnel_summary(days: int = 7) -> dict[str, Any]:
    """Stage counts + simple stage-to-stage conversion rates."""
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT event, COUNT(*)::int AS n
            FROM smb_funnel_events
            WHERE created_at >= %s
            GROUP BY event
            """,
            (since,),
        ).fetchall()
    counts = {str(r[0]): int(r[1]) for r in rows}
    stages = []
    prev_count: int | None = None
    for stage in FUNNEL_STAGES:
        n = counts.get(stage, 0)
        conv_from_prev = None
        if prev_count is not None and prev_count > 0:
            conv_from_prev = round(n / prev_count, 4)
        stages.append(
            {
                "event": stage,
                "count": n,
                "conversion_from_previous": conv_from_prev,
            }
        )
        # Only advance the denominator when the prior stage had traffic;
        # otherwise keep looking for the last non-zero stage.
        if n > 0:
            prev_count = n
    return {
        "days": days,
        "stages": stages,
        "raw_counts": counts,
        "pageviews": counts.get("pageview", 0),
        "source": "smb-copilot first-party funnel events",
    }
