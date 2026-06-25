"""Shared semantic comparison helpers."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9']+")


def token_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def jaccard_similarity(a: str, b: str) -> float:
    sa, sb = token_set(a), token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def divergence_score(original: str, restatement: str) -> float:
    """Higher score means more semantic drift between original and restatement."""
    similarity = jaccard_similarity(original, restatement)
    drift = 1.0 - similarity

    # Penalize when restatement omits high-signal tokens present in the original.
    orig_tokens = token_set(original)
    rest_tokens = token_set(restatement)
    omitted = orig_tokens - rest_tokens
    high_signal = {
        t
        for t in omitted
        if len(t) >= 5
        or t
        in {
            "bomb",
            "weapon",
            "kill",
            "password",
            "secret",
            "jailbreak",
            "malware",
            "api",
            "key",
        }
    }
    omission_boost = min(0.35, 0.08 * len(high_signal))

    # Penalize large length mismatch (common smoothing artifact).
    len_ratio = len(restatement) / max(len(original), 1)
    length_penalty = 0.0
    if len_ratio < 0.35 or len_ratio > 2.5:
        length_penalty = 0.15

    return min(max(drift + omission_boost + length_penalty, 0.0), 1.0)
