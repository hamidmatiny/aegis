"""First-party pageview + funnel collect/summary (Growth impact baseline)."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from aegis_smb_copilot.analytics.funnel import (
    FUNNEL_EVENTS,
    emit_funnel_event,
    funnel_summary,
)
from aegis_smb_copilot.config import settings
from aegis_smb_copilot.db.connection import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


class PageViewIn(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    referrer: str = Field(default="", max_length=1024)
    title: str = Field(default="", max_length=512)
    # Optional typed funnel event. Default pageview keeps the beacon compatible.
    event: str = Field(default="pageview", max_length=64)
    session_id: str = Field(default="", max_length=64)
    meta: dict[str, Any] = Field(default_factory=dict)


def _ua_hash(ua: str) -> str:
    if not ua:
        return ""
    return hashlib.sha256(ua.encode("utf-8", errors="replace")).hexdigest()[:16]


def _normalize_path(path: str) -> str:
    p = path.strip() or "/"
    if not p.startswith("/"):
        p = "/" + p
    # Drop query/hash; keep guide paths intact
    p = p.split("?", 1)[0].split("#", 1)[0]
    if len(p) > 512:
        raise HTTPException(status_code=400, detail="path too long")
    return p


def _require_analytics_read(authorization: str | None) -> None:
    expected_tokens = {
        t.strip()
        for t in (settings.corp_readonly_token, settings.internal_token)
        if t and t.strip()
    }
    if not expected_tokens:
        return
    got = (authorization or "").removeprefix("Bearer ").strip()
    if got not in expected_tokens:
        raise HTTPException(status_code=401, detail="analytics read unauthorized")


@router.post("/collect")
def collect_event(body: PageViewIn, request: Request) -> dict[str, str]:
    """Public beacon — pageviews + optional funnel stages; no cookies required."""
    path = _normalize_path(body.path)
    event = (body.event or "pageview").strip().lower() or "pageview"
    if event not in FUNNEL_EVENTS:
        raise HTTPException(status_code=400, detail=f"unknown event: {event}")

    ua = request.headers.get("user-agent", "")
    pool = get_pool()
    with pool.connection() as conn:
        # Always retain path-level pageviews for SEO / guide baselines.
        if event == "pageview":
            conn.execute(
                """
                INSERT INTO smb_page_views (path, referrer, title, ua_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    path,
                    (body.referrer or "")[:1024],
                    (body.title or "")[:512],
                    _ua_hash(ua),
                ),
            )
    # Funnel table gets every typed event (including pageview for SPA navigations).
    meta = dict(body.meta or {})
    if body.referrer:
        meta.setdefault("referrer", body.referrer[:1024])
    if body.title:
        meta.setdefault("title", body.title[:512])
    emit_funnel_event(
        event,
        path=path,
        session_id=body.session_id or "",
        meta=meta,
    )
    return {"status": "ok"}


@router.get("/summary")
def analytics_summary(
    days: int = 7,
    path_prefix: str = "",
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Aggregate pageviews + funnel stage conversion for Growth.

    Auth: Bearer CORP_READONLY_TOKEN or AEGIS_INTERNAL_TOKEN when either is set
    in the environment. If neither is configured (local dev), open read is allowed.
    """
    _require_analytics_read(authorization)
    days = max(1, min(days, 90))

    since = datetime.now(timezone.utc) - timedelta(days=days)
    prefix = path_prefix.strip()
    pool = get_pool()
    with pool.connection() as conn:
        if prefix:
            rows = conn.execute(
                """
                SELECT path, COUNT(*)::int AS views,
                       MAX(created_at) AS last_seen
                FROM smb_page_views
                WHERE created_at >= %s AND path LIKE %s
                GROUP BY path
                ORDER BY views DESC
                LIMIT 100
                """,
                (since, prefix + "%"),
            ).fetchall()
            total = conn.execute(
                """
                SELECT COUNT(*)::int FROM smb_page_views
                WHERE created_at >= %s AND path LIKE %s
                """,
                (since, prefix + "%"),
            ).fetchone()[0]
        else:
            rows = conn.execute(
                """
                SELECT path, COUNT(*)::int AS views,
                       MAX(created_at) AS last_seen
                FROM smb_page_views
                WHERE created_at >= %s
                GROUP BY path
                ORDER BY views DESC
                LIMIT 100
                """,
                (since,),
            ).fetchall()
            total = conn.execute(
                """
                SELECT COUNT(*)::int FROM smb_page_views
                WHERE created_at >= %s
                """,
                (since,),
            ).fetchone()[0]

    funnel = funnel_summary(days=days)
    return {
        "days": days,
        "path_prefix": prefix or None,
        "total_views": total,
        "by_path": [
            {
                "path": r[0],
                "views": r[1],
                "last_seen": r[2].isoformat() if r[2] else None,
            }
            for r in rows
        ],
        "funnel": funnel,
        "source": "smb-copilot first-party pageviews + funnel events",
        "notes": {
            "pageviews": (
                "smb_page_views stores hard HTML loads + SPA pageview events "
                "posted by the portal tracker. Pre-2026-09-20 beacons were "
                "full-document loads only (no React soft-nav)."
            ),
            "funnel": (
                "smb_funnel_events stores typed stages: signup_started → "
                "signup_completed → inventory_saved → qa_asked → "
                "cve_match_shown → walkthrough_viewed → upgrade_viewed → "
                "upgrade_started → upgrade_completed."
            ),
        },
    }
