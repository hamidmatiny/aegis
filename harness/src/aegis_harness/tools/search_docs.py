"""search_docs -- the LOW-risk starter tool.

Reuses the exact tool_name already registered in policy-engine's real
tool_catalog (see policy-engine/policies/default.yaml) at LOW risk, so
this demonstrates the harness's "always allowed, still audited" path
without needing any new policy YAML. Deliberately trivial and offline: a
substring search over a small in-memory fixture, no network, no
filesystem access, nothing that could plausibly need gating beyond what
the catalog already declares.
"""

from __future__ import annotations

from typing import Any

from aegis_harness.tool import Tool

_FIXTURE_DOCS: dict[str, str] = {
    "onboarding": "New agents should call agent-gate before executing any tool.",
    "billing": "Refunds require a human-approved irreversible action.",
    "security": "Never log a raw credential; agent-gate masks detected ones automatically.",
}


class SearchDocsTool(Tool):
    name = "search_docs"
    description = "Search a small internal documentation fixture by keyword."
    risk_level = "LOW"

    def __init__(self, docs: dict[str, str] | None = None) -> None:
        self._docs = docs if docs is not None else _FIXTURE_DOCS

    def argument_schema(self) -> dict[str, Any]:
        return {"query": "string, a keyword to search for"}

    def execute(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip().lower()
        if not query:
            return "No query provided."
        hits = [
            f"{title}: {body}"
            for title, body in self._docs.items()
            if query in body.lower() or query in title.lower()
        ]
        if not hits:
            return f"No documents matched '{query}'."
        return "\n".join(hits)
