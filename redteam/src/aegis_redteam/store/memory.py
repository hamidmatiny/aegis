"""In-memory bypass pattern store."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aegis_redteam.models import BypassPattern, ProbeResult


class MemoryPatternStore:
    def __init__(self) -> None:
        self._patterns: dict[str, BypassPattern] = {}

    def list_patterns(self) -> list[BypassPattern]:
        return sorted(self._patterns.values(), key=lambda p: p.stored_at, reverse=True)

    def store_probe(self, result: ProbeResult) -> BypassPattern | None:
        if not result.bypassed:
            return None
        pattern_hash = hashlib.sha256(
            f"{result.target}:{result.strategy}:{result.payload}".encode()
        ).hexdigest()
        if pattern_hash in self._patterns:
            return self._patterns[pattern_hash]

        pattern = BypassPattern(
            pattern_hash=pattern_hash,
            attack_id=result.attack_id,
            category=result.category,
            target=result.target,
            strategy=result.strategy,
            payload=result.payload,
            defense_action=result.defense_action,
            fused_score=result.fused_score,
            stored_at=datetime.now(tz=UTC),
        )
        self._patterns[pattern_hash] = pattern
        return pattern
