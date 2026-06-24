#!/usr/bin/env python3
"""Tool-using agent example: agent-gate approval + policy enforcement."""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from aegis_sdk import AegisApprovalRequiredError, AegisPolicyBlockedError, OpenAI


def evaluate_tool_embedded(tool_call: dict) -> dict:
    client = OpenAI()  # embedded mode — calls agent-gate directly
    return client.tools.evaluate(tool_call=tool_call)


def evaluate_tool_http(tool_call: dict) -> dict:
    gate_url = os.environ.get("AEGIS_AGENT_GATE_URL", "http://localhost:8083")
    resp = httpx.post(
        f"{gate_url}/v1/evaluate",
        json={"tenant_id": "default", "mode": "enforce", "tool_call": tool_call},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def print_decision(data: dict) -> None:
    decision = data.get("decision", data)
    status = decision.get("status", "UNKNOWN")
    print(f"RESULT: {status}")
    if decision.get("approval_request_id"):
        print(f"  approval_id: {decision['approval_request_id']}")
        print("  Next: approve via dashboard or:")
        print(
            f"    curl -X POST localhost:8083/v1/approvals/"
            f"{decision['approval_request_id']}/decide "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"approved\": true, \"reviewer_id\": \"demo\", \"comment\": \"ok\"}}'"
        )
    if decision.get("denial_reason"):
        print(f"  reason: {decision['denial_reason']}")
    if data.get("sanitized_tool_call"):
        print("\nSanitized tool call (credentials masked):")
        print(json.dumps(data["sanitized_tool_call"], indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="AEGIS tool-using agent example")
    parser.add_argument(
        "--scenario",
        choices=["safe-search", "irreversible-delete", "credential-leak"],
        required=True,
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Call agent-gate via HTTP instead of embedded SDK",
    )
    args = parser.parse_args()

    scenarios = {
        "safe-search": {
            "title": "Low-risk tool — allowed",
            "tool_call": {
                "tool_name": "search_docs",
                "risk_level": "LOW",
                "arguments": [{"name": "query", "value": "deployment runbook", "taint_level": "TRUSTED"}],
            },
        },
        "irreversible-delete": {
            "title": "Irreversible tool — human approval required",
            "tool_call": {
                "tool_name": "delete_database",
                "risk_level": "IRREVERSIBLE",
                "arguments": [{"name": "db_id", "value": "prod-analytics", "taint_level": "TRUSTED"}],
            },
        },
        "credential-leak": {
            "title": "Tainted credentials in tool args — denied",
            "tool_call": {
                "tool_name": "send_email",
                "risk_level": "MEDIUM",
                "arguments": [
                    {
                        "name": "body",
                        "value": "password: hunter2 api_key=sk-secret-leak-123",
                        "taint_level": "TAINTED",
                        "contains_credentials": True,
                    },
                ],
            },
        },
    }

    spec = scenarios[args.scenario]
    print(f"=== Scenario: {spec['title']} ===\n")
    print("LLM-selected tool call:")
    print(json.dumps(spec["tool_call"], indent=2))
    print()

    try:
        if args.http:
            data = evaluate_tool_http(spec["tool_call"])
        else:
            data = evaluate_tool_embedded(spec["tool_call"])
            if "decision" not in data:
                data = {"decision": data}
    except AegisApprovalRequiredError as exc:
        print("RESULT: AWAITING_HUMAN_APPROVAL")
        print(f"  approval_id: {exc.approval_id}")
        print(f"  tool:        {exc.tool_name}")
        print("\nApprove with:")
        print(
            f"  curl -X POST localhost:8083/v1/approvals/{exc.approval_id}/decide "
            "-H 'Content-Type: application/json' "
            "-d '{\"approved\": true, \"reviewer_id\": \"demo\", \"comment\": \"approved in demo\"}'"
        )
        return 0
    except AegisPolicyBlockedError as exc:
        print("RESULT: DENIED")
        print(f"  layer:  {exc.layer}")
        print(f"  reason: {exc}")
        return 0

    print_decision(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
