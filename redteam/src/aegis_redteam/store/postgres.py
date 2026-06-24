"""Optional Postgres persistence for attack_patterns."""

from __future__ import annotations

import json
import logging
from typing import Any

from aegis_redteam.models import BypassPattern

logger = logging.getLogger(__name__)


class PostgresPatternStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def save(self, pattern: BypassPattern) -> bool:
        try:
            import psycopg  # noqa: PLC0415

            metadata: dict[str, Any] = {
                "attack_id": pattern.attack_id,
                "category": pattern.category,
                "target": pattern.target.value,
                "strategy": pattern.strategy,
                "payload": pattern.payload[:2000],
                "defense_action": pattern.defense_action,
                "fused_score": pattern.fused_score,
            }
            with psycopg.connect(self._database_url) as conn:
                conn.execute(
                    """
                    INSERT INTO attack_patterns (pattern_hash, source, metadata)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (pattern_hash) DO NOTHING
                    """,
                    (pattern.pattern_hash, pattern.source, json.dumps(metadata)),
                )
                conn.commit()
            return True
        except Exception as exc:  # pragma: no cover - optional integration
            logger.warning("postgres pattern store failed: %s", exc)
            return False
