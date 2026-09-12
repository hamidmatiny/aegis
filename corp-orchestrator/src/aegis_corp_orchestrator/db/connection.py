"""Postgres connection pool."""

from __future__ import annotations

from typing import Any

from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        from aegis_corp_orchestrator.config import settings

        _pool = ConnectionPool(
            conninfo=settings.database_url,
            kwargs={"autocommit": True, "connect_timeout": 10},
            open=True,
            min_size=1,
            max_size=10,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _configure(_conn: Any) -> None:
    return None
