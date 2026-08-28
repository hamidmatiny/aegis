"""Apply smb-copilot SQL migrations idempotently at startup."""

from __future__ import annotations

import logging
from pathlib import Path

from aegis_smb_copilot.db.connection import get_pool

logger = logging.getLogger(__name__)


def apply_migrations() -> None:
    """Run bundled ``aegis_smb_copilot/sql/*.sql`` (CREATE IF NOT EXISTS)."""
    sql_dir = Path(__file__).resolve().parent.parent / "sql"
    if not sql_dir.is_dir():
        logger.warning("no sql migration directory at %s — skipping", sql_dir)
        return

    pool = get_pool()
    with pool.connection() as conn:
        for script in sorted(sql_dir.glob("*.sql")):
            conn.execute(script.read_text(encoding="utf-8"))
            logger.info("applied migration %s", script.name)
