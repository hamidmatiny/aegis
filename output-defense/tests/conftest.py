"""Shared pytest fixtures."""

from __future__ import annotations

import os

# Fast stub backends for unit/regression tests (no model downloads or router calls).
os.environ.setdefault("AEGIS_OUTPUT_DEFENSE_TOXICITY_BACKEND", "stub")
os.environ.setdefault("AEGIS_OUTPUT_DEFENSE_PII_BACKEND", "regex")
os.environ.setdefault("AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_BACKEND", "stub")
os.environ.setdefault("AEGIS_OUTPUT_DEFENSE_JUDGE_BACKEND", "stub")

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
