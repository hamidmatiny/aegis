"""Attack fixture corpus structure tests."""

from __future__ import annotations


def test_fixture_counts(all_fixtures) -> None:
    attacks = [f for f in all_fixtures if f.is_attack]
    input_attacks = [f for f in attacks if f.target.value == "input_defense"]
    output_attacks = [f for f in attacks if f.target.value == "output_defense"]
    assert len(all_fixtures) >= 20
    assert len(input_attacks) >= 10
    assert len(output_attacks) >= 10


def test_fixture_targets_and_payloads(attack_fixtures) -> None:
    for fixture in attack_fixtures:
        assert fixture.payload(), f"{fixture.id} missing payload"
