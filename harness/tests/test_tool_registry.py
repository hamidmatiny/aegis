from __future__ import annotations

import pytest

from aegis_harness.tool import Tool, ToolRegistry


class _DummyTool(Tool):
    name = "dummy"
    description = "d"
    risk_level = "LOW"

    def argument_schema(self) -> dict:
        return {}

    def execute(self, arguments: dict) -> str:
        return "done"


def test_register_and_get():
    registry = ToolRegistry()
    tool = _DummyTool()
    registry.register(tool)
    assert registry.get("dummy") is tool
    assert "dummy" in registry
    assert len(registry) == 1
    assert registry.names() == ["dummy"]


def test_get_missing_returns_none():
    registry = ToolRegistry()
    assert registry.get("nope") is None
    assert "nope" not in registry


def test_duplicate_registration_raises():
    registry = ToolRegistry()
    registry.register(_DummyTool())
    with pytest.raises(ValueError):
        registry.register(_DummyTool())


def test_iteration_yields_tools():
    registry = ToolRegistry()
    tool = _DummyTool()
    registry.register(tool)
    assert list(registry) == [tool]
