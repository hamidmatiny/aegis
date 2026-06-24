"""Bypass detection tests."""

from aegis_redteam.probe.bypass import is_bypass


def test_block_is_not_bypass() -> None:
    assert is_bypass("BLOCK", 0.95, 0.50) is False


def test_escalate_is_not_bypass() -> None:
    assert is_bypass("ESCALATE", 0.62, 0.50) is False


def test_allow_low_score_is_bypass() -> None:
    assert is_bypass("ALLOW", 0.12, 0.50) is True


def test_transform_below_threshold_is_bypass() -> None:
    assert is_bypass("TRANSFORM", 0.30, 0.50) is True
