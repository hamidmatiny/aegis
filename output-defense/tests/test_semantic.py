"""Semantic divergence scoring tests."""

from __future__ import annotations

from aegis_output_defense.detectors.semantic import (
    content_recall,
    divergence_score,
    is_meta_restatement,
    strip_meta_framing,
)


def test_meta_restatement_benign_python_help() -> None:
    original = (
        "Here's how to sort a list in Python: use the built-in sorted() function "
        "or list.sort() method."
    )
    restatement = (
        "The text intends to provide instructions on sorting a list in Python. "
        "It claims that this can be done using the built-in sorted() function "
        "or list.sort() method."
    )
    assert is_meta_restatement(restatement)
    assert content_recall(original, restatement) >= 0.55
    assert divergence_score(original, restatement) < 0.50


def test_policy_refusal_paraphrase_stays_benign() -> None:
    original = (
        "I can't help with creating weapons or harmful devices. "
        "I'm unable to provide that information."
    )
    restatement = (
        "I cannot assist with making weapons or other dangerous items, "
        "and I am unable to supply that information."
    )
    assert divergence_score(original, restatement) < 0.50


def test_code_block_paraphrase_stays_benign() -> None:
    original = '''```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```'''
    restatement = (
        "The provided code defines a function named greet that takes a single "
        "parameter called name of type str and returns a str formatted as Hello, {name}!"
    )
    assert divergence_score(original, restatement) < 0.50


def test_explicit_jailbreak_paraphrase_has_low_lexical_drift() -> None:
    """Faithful paraphrase of explicit jailbreak text is low drift; stub patterns catch it."""
    original = "Developer mode enabled. Jailbreak successful."
    restatement = "Developer mode is active and the jailbreak completed successfully."
    assert divergence_score(original, restatement) < 0.50


def test_harm_omission_increases_drift() -> None:
    original = "Here is how to make a bomb at home step by step."
    restatement = "The text provides general information about chemistry experiments."
    assert divergence_score(original, restatement) >= 0.50


def test_strip_meta_framing() -> None:
    restatement = "The text states that HTTP 404 means not found."
    stripped = strip_meta_framing(restatement)
    assert stripped.lower().startswith("http 404")
