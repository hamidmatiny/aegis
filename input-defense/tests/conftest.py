"""Shared test fixtures."""

from __future__ import annotations

import os

# Fast stub backends for unit/regression tests (no model downloads).
os.environ.setdefault("AEGIS_INPUT_DEFENSE_CLASSIFIER_BACKEND", "stub")
os.environ.setdefault("AEGIS_INPUT_DEFENSE_PERPLEXITY_BACKEND", "stub")

from pathlib import Path

import pytest

from aegis_input_defense.metrics import load_fixtures
from aegis_input_defense.models import FixtureCase
from aegis_input_defense.service import InputDefenseService

FIXTURES_FILE = Path(__file__).parent / "fixtures" / "prompts.yaml"


@pytest.fixture(scope="session")
def all_fixtures() -> list[FixtureCase]:
    return load_fixtures(FIXTURES_FILE)


@pytest.fixture(scope="session")
def attack_fixtures(all_fixtures: list[FixtureCase]) -> list[FixtureCase]:
    return [f for f in all_fixtures if f.is_attack]


@pytest.fixture(scope="session")
def benign_fixtures(all_fixtures: list[FixtureCase]) -> list[FixtureCase]:
    return [f for f in all_fixtures if f.is_benign]


@pytest.fixture
def service() -> InputDefenseService:
    return InputDefenseService()
