"""delete_database -- the IRREVERSIBLE-risk starter tool.

Reuses the exact tool_name already registered in policy-engine's real
tool_catalog at IRREVERSIBLE risk, which trips the real
`require-approval-irreversible` tool_rule (default.yaml) unconditionally
-- this is the tool that proves the harness actually pauses and waits
for a human decision via agent-gate's `/v1/approvals/{id}/decide` before
ever reaching `execute()`, not just that it asks nicely.

Deliberately never touches a real database: "deletes" a sandboxed local
file that this tool itself creates if missing, so triggering the real
approval flow in a demo or test is completely harmless.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis_harness.tool import Tool

DEFAULT_SANDBOX_DB_PATH = Path("/tmp/aegis-harness-sandbox/fake_database.txt")


class DeleteDatabaseTool(Tool):
    name = "delete_database"
    description = (
        "Delete a database. Operates on a local sandboxed placeholder file, "
        "never a real database -- exists to exercise the human-approval flow safely."
    )
    risk_level = "IRREVERSIBLE"

    def __init__(self, sandbox_path: Path | None = None) -> None:
        self._sandbox_path = sandbox_path or DEFAULT_SANDBOX_DB_PATH

    def argument_schema(self) -> dict[str, Any]:
        return {"database_name": "string, name of the database to delete"}

    def execute(self, arguments: dict[str, Any]) -> str:
        database_name = str(arguments.get("database_name", "")).strip()
        if not database_name:
            return "Error: 'database_name' is required."
        self._sandbox_path.parent.mkdir(parents=True, exist_ok=True)
        if self._sandbox_path.exists():
            self._sandbox_path.unlink()
            return f"Deleted sandboxed placeholder for database '{database_name}'."
        return f"Database '{database_name}' had no sandboxed placeholder to delete (already gone)."
