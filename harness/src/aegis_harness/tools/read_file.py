"""read_file -- a MEDIUM-risk starter tool, new in operator-platform phase 2.

New tool_catalog entry (see policy-engine/policies/default.yaml) at
MEDIUM, the same tier as send_email: not destructive, but file read is a
well-known reconnaissance/exfiltration step for a misbehaving or
prompt-injected agent in real deployments, so it's registered rather
than left to fall back to this class's own declared LOW default -- the
catalog entry is the one that actually governs a real run (agent-gate
takes the higher of declared vs catalog, see tool.py's docstring).

Confined to a sandbox root directory, never the real filesystem: every
requested path is resolved against `sandbox_root` and rejected outright
if it would resolve outside it (`../../etc/passwd`, an absolute path,
a symlink escaping the root, etc.) -- the same "never touch anything
real" pattern as send_email's outbox and delete_database's placeholder
file, applied to a path-traversal-prone operation instead of a
fixed-location one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis_harness.tool import Tool

DEFAULT_SANDBOX_ROOT = Path("/tmp/aegis-harness-sandbox/files")


class PathEscapesSandboxError(ValueError):
    """Raised when a requested path resolves outside the sandbox root."""


def resolve_within_sandbox(sandbox_root: Path, relative_path: str) -> Path:
    """Resolve `relative_path` against `sandbox_root` and refuse anything
    that escapes it. Shared by read_file and write_file so both tools
    enforce identical containment logic rather than two hand-rolled
    copies that could quietly drift apart."""
    sandbox_root.mkdir(parents=True, exist_ok=True)
    root = sandbox_root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise PathEscapesSandboxError(
            f"'{relative_path}' resolves outside the sandbox root, refusing"
        )
    return candidate


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read a text file's contents by path. Confined to a local sandbox "
        "directory, never the real filesystem."
    )
    risk_level = "MEDIUM"

    def __init__(self, sandbox_root: Path | None = None) -> None:
        self._sandbox_root = sandbox_root or DEFAULT_SANDBOX_ROOT

    def argument_schema(self) -> dict[str, Any]:
        return {"path": "string, path relative to the sandbox root"}

    def execute(self, arguments: dict[str, Any]) -> str:
        relative_path = str(arguments.get("path", "")).strip()
        if not relative_path:
            return "Error: 'path' is required."
        try:
            target = resolve_within_sandbox(self._sandbox_root, relative_path)
        except PathEscapesSandboxError as exc:
            return f"Error: {exc}"
        if not target.exists():
            return f"Error: '{relative_path}' does not exist in the sandbox."
        if not target.is_file():
            return f"Error: '{relative_path}' is not a file."
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: '{relative_path}' is not valid UTF-8 text."
