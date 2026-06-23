"""Verify fixture corpus structure."""

from aegis_input_defense.metrics import load_fixtures


def test_fixture_counts(all_fixtures) -> None:
    attacks = [f for f in all_fixtures if f.is_attack]
    benign = [f for f in all_fixtures if f.is_benign]
    assert len(all_fixtures) >= 35
    assert len(attacks) >= 20
    assert len(benign) >= 10


def test_fixture_categories(all_fixtures) -> None:
    categories = {f.category for f in all_fixtures if f.is_attack}
    required = {
        "direct_injection",
        "roleplay_jailbreak",
        "encoding_obfuscation",
        "indirect_injection",
        "multi_turn_escalation",
    }
    assert required.issubset(categories)


def test_fixtures_load_from_disk() -> None:
    fixtures = load_fixtures()
    assert all(f.id and f.text for f in fixtures)
