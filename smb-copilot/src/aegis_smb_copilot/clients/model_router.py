"""HTTP client for model-router (embeddings + chat)."""

from __future__ import annotations

from typing import Any

import httpx

from aegis_smb_copilot.config import settings


class ModelRouterError(RuntimeError):
    """Raised when model-router returns a non-success response."""


def _auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.internal_token:
        headers["Authorization"] = f"Bearer {settings.internal_token}"
    return headers


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

    url = settings.model_router_url.rstrip("/") + "/v1/embeddings"
    own_client = client is None
    http = client or httpx.Client(timeout=60.0)
    try:
        resp = http.post(url, json=payload, headers=_auth_headers())
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
    ordered = sorted(data, key=lambda row: int(row.get("index", 0)))
    for row in ordered:
        emb = row.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise ModelRouterError(f"missing embedding in row: {row!r}")
        vectors.append([float(x) for x in emb])
    return vectors


def chat_completion(
    messages: list[dict[str, str]],
    *,
    client: httpx.Client | None = None,
) -> str:
    """Call ``POST /v1/chat/completions`` and return assistant text."""
    payload: dict[str, Any] = {
        "messages": messages,
        "model": settings.chat_model,
        "stream": False,
    }
    if settings.chat_provider:
        payload["provider"] = settings.chat_provider

    url = settings.model_router_url.rstrip("/") + "/v1/chat/completions"
    own_client = client is None
    http = client or httpx.Client(timeout=120.0)
    try:
        resp = http.post(url, json=payload, headers=_auth_headers())
    finally:
        if own_client:
            http.close()

    if resp.status_code >= 400:
        raise ModelRouterError(
            f"model-router chat HTTP {resp.status_code}: {resp.text[:500]}"
        )

    body = resp.json()
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ModelRouterError(f"model-router chat missing choices: {body!r}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ModelRouterError(f"model-router chat empty content: {body!r}")
    return content.strip()
