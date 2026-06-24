"""Bypass detection logic."""

from __future__ import annotations


def is_bypass(action: str, fused_score: float, threshold: float) -> bool:
    """
    Return True when the attack evaded defense blocking.

    Bypass = defense allowed or scored below detection threshold.
    BLOCK and ESCALATE are treated as caught.
    """
    normalized = action.upper()
    if normalized in {"BLOCK", "ESCALATE"}:
        return False
    if fused_score >= threshold:
        return False
    return True
