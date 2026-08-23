"""HTTP client for model-router (embeddings only)."""

from __future__ import annotations

from typing import Any

import httpx

from aegis_smb_copilot.config import settings


class ModelRouterError(RuntimeError):
    """Raised when model-router returns a non-success embeddings response."""


def embed_texts(
    texts: list[str],
    *,
    client: httpx.Client | None = None,
) -> list[list[float]]:
    """Call ``POST /v1/embeddings`` and return one vector per input string."""
    if not texts:
        return []

    payload: dict[str, Any] = {
        "input": texts if len(texts) > 1 else texts[0],
        "model": settings.embedding_model,
    }
    if settings.embedding_provider:
        payload["provider"] = settings.embedding_provider

    headers = {"Content-Type": "application/json"}
    if settings.internal_token:
        headers["Authorization"] = f"Bearer {settings.internal_token}"

    url = settings.model_router_url.rstrip("/") + "/v1/embeddings"
    own_client = client is None
    http = client or httpx.Client(timeout=60.0)
    try:
        resp = http.post(url, json=payload, headers=headers)
    finally:
        if own_client:
            http.close()

    if resp.status_code >= 400:
        raise ModelRouterError(
            f"model-router embeddings HTTP {resp.status_code}: {resp.text[:500]}"
        )

    body = resp.json()
    data = body.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise ModelRouterError(
            f"model-router embeddings returned unexpected data length: {body!r}"
        )

    vectors: list[list[float]] = []
    # OpenAI may return data unordered; sort by index.
    ordered = sorted(data, key=lambda row: int(row.get("index", 0)))
    for row in ordered:
        emb = row.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise ModelRouterError(f"missing embedding in row: {row!r}")
        vectors.append([float(x) for x in emb])
    return vectors
