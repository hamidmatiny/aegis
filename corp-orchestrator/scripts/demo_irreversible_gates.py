#!/usr/bin/env python3
"""Demonstrate IRREVERSIBLE corp tools require human approval via agent-gate.

Does not execute the tools — only POST /v1/evaluate and print the decision.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

GATE = os.environ.get("AGENT_GATE_URL", "http://127.0.0.1:8083").rstrip("/")
KEY = (os.environ.get("AEGIS_AGENT_GATE_API_KEYS") or "").split(",")[0].strip()


def evaluate(tool_name: str, risk_level: str, arguments: dict) -> dict:
    payload = {
        "tenant_id": "default",
        "mode": "enforce",
        "tool_call": {
            "tool_name": tool_name,
            "agent_id": "corp-irreversible-demo",
            "risk_level": risk_level,
            "arguments": [{"name": k, "value": v} for k, v in arguments.items()],
        },
    }
    req = urllib.request.Request(
        f"{GATE}/v1/evaluate",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {KEY}"} if KEY else {}),
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    if not KEY:
        print("AEGIS_AGENT_GATE_API_KEYS required", file=sys.stderr)
        return 2
    cases = [
        (
            "corp_apply_cve_write",
            "IRREVERSIBLE",
            {
                "cve_id": "CVE-2099-0001",
                "product_pattern": "demo-only",
                "summary": "demo",
            },
        ),
        (
            "corp_publish_outreach",
            "IRREVERSIBLE",
            {"draft_json": '{"subject":"demo"}'},
        ),
    ]
    ok = True
    for name, risk, args in cases:
        decision = evaluate(name, risk, args)
        status = decision.get("status") or decision.get("decision") or decision
        # agent-gate returns status at top level typically
        print(name, "=>", json.dumps(decision)[:500])
        text = json.dumps(decision)
        if "AWAITING_HUMAN_APPROVAL" not in text and "awaiting" not in text.lower():
            # Also accept nested
            if decision.get("status") != "AWAITING_HUMAN_APPROVAL":
                print("FAIL: expected AWAITING_HUMAN_APPROVAL for", name)
                ok = False
        else:
            print("OK: IRREVERSIBLE escalated for", name)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
