"""Normalize intake answers and persist infra_memory rows (no embeddings yet)."""

from __future__ import annotations

import re
from uuid import UUID

from aegis_smb_copilot.db.connection import get_pool
from aegis_smb_copilot.onboarding.schema import (
    InfraProfile,
    InfraProfileItem,
    IntakeAnswer,
    RegisterResponse,
)
from aegis_smb_copilot.tenancy.auth import generate_api_key, hash_api_key

_VERSION_RE = re.compile(
    r"(?P<name>[a-z][a-z0-9_+-]*)[ /\-_]*(?P<major>\d+)(?:\.(?P<minor>\d+))?",
    re.IGNORECASE,
)

_KNOWN_ALIASES: dict[str, str] = {
    "postgresql": "postgres",
    "pg": "postgres",
    "psql": "postgres",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "gke": "gke",
    "eks": "eks",
    "aks": "aks",
}


def normalize_pair(category: str, value: str) -> tuple[str, str]:
    """Return (category, normalized_value); prefer major.minor product tags."""
    cat = category.strip().lower().replace(" ", "_")
    raw = " ".join(value.strip().lower().split())
    if not cat or not raw:
        raise ValueError("category and value are required")

    match = _VERSION_RE.search(raw)
    if match:
        name = match.group("name").lower()
        name = _KNOWN_ALIASES.get(name, name)
        major = match.group("major")
        minor = match.group("minor")
        if minor is not None:
            return cat, f"{name}-{major}.{minor}.x"
        return cat, f"{name}-{major}.x"

    token = re.sub(r"[^a-z0-9.+_-]+", "-", raw).strip("-")
    token = _KNOWN_ALIASES.get(token, token)
    if not token:
        raise ValueError(f"could not normalize value for category={cat!r}")
    return cat, token


def register_tenant(slug: str, tier: str = "standard") -> RegisterResponse:
    api_key = generate_api_key()
    digest = hash_api_key(api_key)
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO tenants (slug, tier, api_key_hash)
            VALUES (%s, %s, %s)
            RETURNING id, slug, tier
            """,
            (slug, tier, digest),
        ).fetchone()
    if row is None:
        raise RuntimeError("tenant insert returned no row")
    tenant_id, out_slug, out_tier = row[0], row[1], row[2]
    if not isinstance(tenant_id, UUID):
        tenant_id = UUID(str(tenant_id))
    return RegisterResponse(
        tenant_id=tenant_id,
        slug=str(out_slug),
        tier=str(out_tier),
        api_key=api_key,
    )


def store_intake(tenant_id: UUID, answers: list[IntakeAnswer]) -> InfraProfile:
    """Normalize answers and insert infra_memory rows for ``tenant_id`` only."""
    pairs: list[tuple[str, str]] = []
    for answer in answers:
        pairs.append(normalize_pair(answer.category, answer.value))

    items: list[InfraProfileItem] = []
    pool = get_pool()
    with pool.connection() as conn:
        with conn.transaction():
            for category, normalized_value in pairs:
                row = conn.execute(
                    """
                    INSERT INTO infra_memory (tenant_id, category, normalized_value, embedding)
                    VALUES (%s, %s, %s, NULL)
                    RETURNING id, category, normalized_value
                    """,
                    (tenant_id, category, normalized_value),
                ).fetchone()
                if row is None:
                    raise RuntimeError("infra_memory insert returned no row")
                item_id, cat, norm = row[0], row[1], row[2]
                if not isinstance(item_id, UUID):
                    item_id = UUID(str(item_id))
                items.append(
                    InfraProfileItem(
                        id=item_id,
                        category=str(cat),
                        normalized_value=str(norm),
                    )
                )

    return InfraProfile(tenant_id=tenant_id, items=items)
