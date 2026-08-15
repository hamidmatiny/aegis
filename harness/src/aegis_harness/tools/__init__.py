"""Built-in starter tools -- three risk tiers, each reusing a real
tool_name already registered in policy-engine's tool_catalog, so the
governance paths they exercise (allow, allow-and-audited,
escalate-to-human-approval) are the platform's real ones, not a demo
stand-in for them.

`default_tool_registry()` is a convenience for the CLI and for tests --
real callers are free to build their own `ToolRegistry` with any subset
of these plus their own tools.
"""

from __future__ import annotations

from aegis_harness.tool import ToolRegistry
from aegis_harness.tools.delete_database import DeleteDatabaseTool
from aegis_harness.tools.search_docs import SearchDocsTool
from aegis_harness.tools.send_email import SendEmailTool

__all__ = [
    "DeleteDatabaseTool",
    "SearchDocsTool",
    "SendEmailTool",
    "default_tool_registry",
]


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SearchDocsTool())
    registry.register(SendEmailTool())
    registry.register(DeleteDatabaseTool())
    return registry
