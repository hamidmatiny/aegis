"""Built-in starter tools -- phase 1 shipped three (search_docs,
send_email, delete_database), each reusing a real tool_name already
registered in policy-engine's tool_catalog. Phase 2 (operator-platform
"tools/skills library") adds four more (calculator, http_get, read_file,
write_file) specifically chosen to fill the one real gap phase 1 left:
every risk tier policy-engine defines -- LOW, MEDIUM, HIGH, IRREVERSIBLE
(see policy-engine/internal/engine/risk.go) -- is now exercised by at
least one starter tool, where phase 1 only reached LOW/MEDIUM/
IRREVERSIBLE and left HIGH completely untested (write_file is the first
to use it).

Adding tool #8 (or #800) later is unchanged from phase 1: implement
`Tool` (tool.py) and register an instance here or in a caller's own
registry -- this file deliberately still has no plugin discovery or
entry_points magic, by the same design choice tool.py's `ToolRegistry`
already documents. Growing the library is about adding more tools this
way, not about building a bigger loading mechanism.

`default_tool_registry()` is a convenience for the CLI and for tests --
real callers are free to build their own `ToolRegistry` with any subset
of these plus their own tools.
"""

from __future__ import annotations

from aegis_harness.tool import ToolRegistry
from aegis_harness.tools.calculator import CalculatorTool
from aegis_harness.tools.delete_database import DeleteDatabaseTool
from aegis_harness.tools.http_get import HttpGetTool
from aegis_harness.tools.read_file import ReadFileTool
from aegis_harness.tools.search_docs import SearchDocsTool
from aegis_harness.tools.send_email import SendEmailTool
from aegis_harness.tools.write_file import WriteFileTool

__all__ = [
    "CalculatorTool",
    "DeleteDatabaseTool",
    "HttpGetTool",
    "ReadFileTool",
    "SearchDocsTool",
    "SendEmailTool",
    "WriteFileTool",
    "default_tool_registry",
]


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SearchDocsTool())
    registry.register(SendEmailTool())
    registry.register(DeleteDatabaseTool())
    registry.register(CalculatorTool())
    registry.register(HttpGetTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    return registry
