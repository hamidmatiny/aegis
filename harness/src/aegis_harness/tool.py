"""Tool interface and registry for the AEGIS harness.

This is the one extensibility point the whole harness is built around:
adding tool #4 (or #400) later means writing a class that implements
`Tool` and registering an instance of it -- nothing in `loop.py` ever
needs to change. The loop only ever sees this interface, never a
tool's real implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


class Tool(ABC):
    """Base class every harness tool implements.

    `risk_level` should match a value governed by policy-engine's
    `tool_catalog` (see policy-engine/policies/default.yaml) when one is
    registered for this tool's `name` -- the catalog's risk_level always
    wins over whatever is declared here (agent-gate takes the higher of
    the two, by design, so a tool can't under-declare its own risk to
    dodge the human-approval gate). Declaring the real risk here anyway
    keeps this class self-documenting and gives agent-gate a sane
    starting point for any tool that ISN'T yet registered in the catalog.
    """

    name: str
    description: str
    risk_level: str = "LOW"

    @abstractmethod
    def argument_schema(self) -> dict[str, Any]:
        """A minimal JSON-schema-shaped dict describing this tool's
        arguments, included in the system prompt so the model knows what
        it can pass. Keep this small and honest -- it's read by a model,
        not validated as real JSON Schema."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> str:
        """Actually perform the tool's action and return a short text
        result to feed back to the model. Only ever called by the loop
        after an ALLOWED decision from agent-gate -- see loop.py's
        `_execute_after_gate` for the one call site. Raise any exception
        on failure; the loop catches it and feeds an error message back
        to the model rather than crashing the whole run."""
        raise NotImplementedError


@dataclass
class ToolRegistry:
    """A name -> Tool lookup, handed to the harness loop at construction
    time. Deliberately just a dict wrapper -- no plugin discovery, no
    entry_points magic. Extending the tool set later is exactly:

        registry = ToolRegistry()
        registry.register(MyNewTool())
    """

    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def names(self) -> list[str]:
        return sorted(self._tools)
