"""write_file -- a HIGH-risk starter tool, new in operator-platform phase 2.

The first starter tool to actually exercise the HIGH tier of
policy-engine's four-level risk ladder (LOW < MEDIUM < HIGH <
IRREVERSIBLE -- see policy-engine/internal/engine/risk.go). Every prior
starter tool (search_docs, send_email, delete_database) only ever
exercised LOW, MEDIUM, and IRREVERSIBLE, leaving HIGH completely
untested by this harness. New tool_catalog entry at HIGH (see
policy-engine/policies/default.yaml).

Honest disclosure: the default policy pack has no tool_rule keyed
specifically on HIGH today (only `require-approval-irreversible`, keyed
on IRREVERSIBLE) -- a HIGH-risk call here still falls through to
`settings.default_action: allow`, identically to a MEDIUM one, under
this pack. Declaring it HIGH is still the operationally correct,
honest thing to do (overwriting/creating file content is a real
integrity risk one tier above a read), and it's what lets an operator
who *does* want stricter-than-default handling add a HIGH-specific
tool_rule later without touching this tool's code at all -- the
declared risk_level is exactly the lever that rule would key on.

Confined to a sandbox root directory via the same containment helper
read_file.py uses (`resolve_within_sandbox`), so this can create or
overwrite files only inside that sandbox, never anywhere on the real
filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis_harness.tool import Tool
from aegis_harness.tools.read_file import (
    DEFAULT_SANDBOX_ROOT,
    PathEscapesSandboxError,
    resolve_within_sandbox,
)


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Create or overwrite a text file by path with the given content. "
        "Confined to a local sandbox directory, never the real filesystem."
    )
    risk_level = "HIGH"

    def __init__(self, sandbox_root: Path | None = None) -> None:
        self._sandbox_root = sandbox_root or DEFAULT_SANDBOX_ROOT

    def argument_schema(self) -> dict[str, Any]:
        return {
            "path": "string, path relative to the sandbox root",
            "content": "string, text content to write",
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        relative_path = str(arguments.get("path", "")).strip()
        if not relative_path:
            return "Error: 'path' is required."
        content = arguments.get("content", "")
        if not isinstance(content, str):
            return "Error: 'content' must be a string."
        try:
            target = resolve_within_sandbox(self._sandbox_root, relative_path)
        except PathEscapesSandboxError as exc:
            return f"Error: {exc}"
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(content, encoding="utf-8")
        verb = "Overwrote" if existed else "Created"
        return f"{verb} '{relative_path}' ({len(content)} chars) in the sandbox."
