"""Fixture corpus structure tests."""

from __future__ import annotations


def test_fixture_counts(all_fixtures) -> None:
    attacks = [f for f in all_fixtures if f.is_attack]
    benign = [f for f in all_fixtures if f.is_benign]
    assert len(all_fixtures) >= 40
    assert len(attacks) >= 28
    assert len(benign) >= 12


def test_attack_categories(attack_fixtures) -> None:
    categories = {f.category for f in attack_fixtures}
    expected = {"leaked_pii", "toxic_content", "jailbreak_completion", "hallucination_incoherent"}
    assert expected.issubset(categories)
