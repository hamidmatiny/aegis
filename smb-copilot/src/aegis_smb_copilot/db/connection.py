"""Postgres connection pool with pgvector registration."""

from __future__ import annotations

from typing import Any

from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def _configure(conn: Any) -> None:
    register_vector(conn)


def get_pool() -> ConnectionPool:
    """Return the process-wide connection pool, creating it on first use."""
    global _pool
    if _pool is None:
        from aegis_smb_copilot.config import settings as live_settings

        _pool = ConnectionPool(
            conninfo=live_settings.database_url,
            kwargs={"autocommit": True, "connect_timeout": 10},
            configure=_configure,
            open=True,
            min_size=1,
            max_size=10,
        )
    return _pool


def close_pool() -> None:
    """Close the pool if it was opened."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
