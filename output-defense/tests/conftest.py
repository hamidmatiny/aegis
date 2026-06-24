"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from aegis_output_defense.metrics import load_fixtures
from aegis_output_defense.service import OutputDefenseService


@pytest.fixture
def service() -> OutputDefenseService:
    return OutputDefenseService()


@pytest.fixture
def all_fixtures():
    return load_fixtures()


@pytest.fixture
def attack_fixtures(all_fixtures):
    return [f for f in all_fixtures if f.is_attack]


@pytest.fixture
def benign_fixtures(all_fixtures):
    return [f for f in all_fixtures if f.is_benign]
