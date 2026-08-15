"""send_email -- the MEDIUM-risk starter tool.

Reuses the exact tool_name already registered in policy-engine's real
tool_catalog at MEDIUM risk. There is no `block`/`escalate_to_judge`
tool_rule keyed on MEDIUM specifically today (see default.yaml's
tool_rules) -- it falls through to `settings.default_action: allow`,
same as this tool's real production behavior would -- so this
demonstrates the "allowed, but every send is on the audit trail via
agent-gate's own EmitToolGate" path, distinct from search_docs's
zero-scrutiny LOW path.

Deliberately never sends real email: writes to a local "outbox" file
instead, so this is safe to actually execute in a demo or test.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from aegis_harness.tool import Tool

DEFAULT_OUTBOX_PATH = Path("/tmp/aegis-harness-sandbox/outbox.jsonl")


class SendEmailTool(Tool):
    name = "send_email"
    description = "Send an email. Writes to a local sandboxed outbox, never a real mail server."
    risk_level = "MEDIUM"

    def __init__(self, outbox_path: Path | None = None) -> None:
        self._outbox_path = outbox_path or DEFAULT_OUTBOX_PATH

    def argument_schema(self) -> dict[str, Any]:
        return {
            "to": "string, recipient address",
            "subject": "string",
            "body": "string",
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        to = str(arguments.get("to", "")).strip()
        subject = str(arguments.get("subject", "")).strip()
        body = str(arguments.get("body", "")).strip()
        if not to:
            return "Error: 'to' is required."
        record = {"to": to, "subject": subject, "body": body, "sent_at": time.time()}
        self._outbox_path.parent.mkdir(parents=True, exist_ok=True)
        with self._outbox_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return f"Queued email to {to} (subject: {subject!r}) in the local outbox."
