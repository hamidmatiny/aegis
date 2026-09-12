#!/usr/bin/env python3
"""Demonstrate corp gate escalations + deferred human approval loop.

1) Five HIGH/IRREVERSIBLE corp tools return AWAITING_HUMAN_APPROVAL.
2) Full loop: park pending → time passes → POST /v1/tasks/{id}/decide
   → tool actually executes → task status done with tool_result.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

GATE = os.environ.get("AGENT_GATE_URL", "http://127.0.0.1:8083").rstrip("/")
CORP = os.environ.get("CORP_ORCHESTRATOR_URL", "http://127.0.0.1:8094").rstrip("/")
KEY = (os.environ.get("AEGIS_AGENT_GATE_API_KEYS") or "").split(",")[0].strip()
REVIEWER = (os.environ.get("AEGIS_AGENT_GATE_REVIEWER_KEYS") or "").split(",")[0].strip()
TOKEN = os.environ.get("AEGIS_INTERNAL_TOKEN") or ""


def _http(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"{method} {url} -> {exc.code}: {detail}") from exc


def evaluate(tool_name: str, risk_level: str, arguments: dict) -> dict:
    return _http(
        "POST",
        f"{GATE}/v1/evaluate",
        {
            "tenant_id": "default",
            "mode": "enforce",
            "tool_call": {
                "tool_name": tool_name,
                "agent_id": "corp-irreversible-demo",
                "risk_level": risk_level,
                "arguments": [{"name": k, "value": v} for k, v in arguments.items()],
            },
        },
        {"Authorization": f"Bearer {KEY}"} if KEY else {},
    )


def corp(method: str, path: str, body: dict | None = None) -> dict:
    return _http(
        method,
        f"{CORP}{path}",
        body,
        {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {},
    )


def main() -> int:
    if not KEY or not TOKEN or not REVIEWER:
        print(
            "Need AEGIS_AGENT_GATE_API_KEYS, AEGIS_AGENT_GATE_REVIEWER_KEYS, AEGIS_INTERNAL_TOKEN",
            file=sys.stderr,
        )
        return 2

    escalate_cases = [
        (
            "corp_apply_cve_write",
            "IRREVERSIBLE",
            {"cve_id": "CVE-2099-0001", "product_pattern": "demo-only", "summary": "demo"},
        ),
        ("corp_publish_outreach", "IRREVERSIBLE", {"draft_json": '{"subject":"demo"}'}),
        (
            "corp_propose_cve_write",
            "HIGH",
            {
                "cve_id": "CVE-2099-HIGH",
                "product_pattern": "demo",
                "reviewer_agent_id": str(uuid4()),
                "notes": "demo propose",
            },
        ),
        (
            "corp_draft_outreach",
            "HIGH",
            {"subject": "demo", "body": "draft only", "channel": "email"},
        ),
        ("corp_redteam_run", "HIGH", {}),
    ]

    ok = True
    print("=== evaluate escalations (5 tools) ===")
    for name, risk, args in escalate_cases:
        decision = evaluate(name, risk, args)
        text = json.dumps(decision)
        status = (decision.get("decision") or {}).get("status") or decision.get("status")
        print(f"{name} => {status}")
        if "AWAITING_HUMAN_APPROVAL" not in text:
            print("FAIL: expected AWAITING_HUMAN_APPROVAL for", name)
            ok = False
        else:
            print("OK: escalated", name)

    print("\n=== deferred approval full loop (IRREVERSIBLE execute) ===")
    cve_id = f"CVE-2099-{int(time.time()) % 100000}"
    parked = corp(
        "POST",
        "/v1/tasks/park-pending",
        {
            "department": "cybersecurity",
            "team": "threat_intel",
            "tool_name": "corp_apply_cve_write",
            "risk_level": "IRREVERSIBLE",
            "arguments": {
                "cve_id": cve_id,
                "product_pattern": "deferred-demo",
                "summary": "deferred approval insert",
            },
            "input": f"Parked IRREVERSIBLE apply for {cve_id}",
        },
    )
    print("parked =>", json.dumps(parked)[:600])
    task_id = parked.get("task_id")
    if not task_id or not parked.get("pending_approval"):
        print("FAIL: park-pending did not return pending_approval")
        return 1

    print("simulating owner delay (3s)...")
    time.sleep(3)

    decided = corp(
        "POST",
        f"/v1/tasks/{task_id}/decide",
        {"approved": True, "comment": "deferred approval demo — approve after delay"},
    )
    print("decide =>", json.dumps(decided)[:900])
    if decided.get("status") != "done":
        print("FAIL: expected status=done after approve")
        ok = False
    result = decided.get("result") or {}
    tool_result = result.get("tool_result") if isinstance(result, dict) else None
    if not tool_result:
        print("FAIL: tool did not execute after approval")
        ok = False
    else:
        print("OK: tool executed post-approval:", tool_result)
        if '"applied": true' not in tool_result.replace(" ", "").lower() and '"applied":true' not in tool_result.replace(" ", ""):
            # tolerate spacing in json
            if "applied" not in tool_result or "true" not in tool_result:
                print("WARN: tool_result missing applied=true:", tool_result)

    # Second loop: force re-issue path by parking with a dead approval id.
    print("\n=== re-issue path (stale approval id) ===")
    parked2 = corp(
        "POST",
        "/v1/tasks/park-pending",
        {
            "department": "sales",
            "team": "growth",
            "tool_name": "corp_draft_outreach",
            "risk_level": "HIGH",
            "approval_request_id": "appr-dead-stale-id-for-reissue",
            "arguments": {
                "subject": "reissue-demo",
                "body": "should re-evaluate then execute",
                "channel": "email",
            },
            "input": "Parked with stale approval id",
        },
    )
    task2 = parked2.get("task_id")
    print("parked stale =>", task2)
    time.sleep(1)
    decided2 = corp(
        "POST",
        f"/v1/tasks/{task2}/decide",
        {"approved": True, "comment": "reissue path"},
    )
    print("reissue decide =>", json.dumps(decided2)[:700])
    res2 = decided2.get("result") or {}
    if decided2.get("status") != "done" or not (isinstance(res2, dict) and res2.get("tool_result")):
        print("FAIL: reissue path did not execute tool")
        ok = False
    elif not res2.get("reissued"):
        print("FAIL: expected reissued=true")
        ok = False
    else:
        print("OK: reissued and executed:", str(res2.get("tool_result"))[:300])

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
