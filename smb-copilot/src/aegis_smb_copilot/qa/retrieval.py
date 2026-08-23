"""Tenant-scoped pgvector retrieval for Q&A."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from aegis_smb_copilot.clients.model_router import embed_texts
from aegis_smb_copilot.db.connection import get_pool


@dataclass(frozen=True)
class RetrievedMemory:
    id: UUID
    category: str
    normalized_value: str
    score: float


def retrieve_infra_context(
    tenant_id: UUID,
    question: str,
    *,
    top_k: int | None = None,
) -> list[RetrievedMemory]:
    """Embed ``question`` and return top-N infra_memory rows for ``tenant_id`` only."""
    q = question.strip()
    if not q:
        return []

    from aegis_smb_copilot.config import settings as live_settings

    k = top_k if top_k is not None else live_settings.qa_top_k
    if k < 1:
        return []

    vector = embed_texts([q])[0]
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, category, normalized_value,
                   (1 - (embedding <=> %s::vector)) AS score
            FROM infra_memory
            WHERE tenant_id = %s
              AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, tenant_id, vector, k),
        ).fetchall()

    out: list[RetrievedMemory] = []
    for row in rows:
        item_id, category, normalized_value, score = row
        if not isinstance(item_id, UUID):
            item_id = UUID(str(item_id))
        out.append(
            RetrievedMemory(
                id=item_id,
                category=str(category),
                normalized_value=str(normalized_value),
                score=float(score) if score is not None else 0.0,
            )
        )
    return out
