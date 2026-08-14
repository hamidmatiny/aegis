#!/usr/bin/env python3
"""Flag rogue-agent tool use (OWASP ASI10) from audit's TOOL_GATE receipts.

The audit service (audit/internal/store/postgres.go) has no server-side
filter for agent_id or tool_name -- both live inside the JSONB
`tool_decision` payload, and the query API (audit/internal/models/receipt.go
QueryRequest) only supports tenant_id, event_type, trace_id, start_time,
end_time, limit, cursor. So this script fetches every TOOL_GATE receipt
in the requested window via cursor pagination and does the agent_id /
tool_name pattern analysis client-side.

Signal: for each agent_id, walk its tool calls in chronological order and
track the set of distinct tool_names already seen. Once an agent has an
established baseline (it has called at least one tool before), any call
to a tool_name outside that baseline is flagged as a first-time-seen tool
-- i.e. a plausible ASI10 rogue-agent signal (an agent suddenly reaching
for capabilities it has never used before). An agent's very first-ever
call is never flagged (everything is "first seen" trivially at that
point, so flagging it would just be noise).

The audit service is bound to 127.0.0.1 only in every AEGIS compose file
(see deploy/oracle/docker-compose.demo.yml / docker-compose.yml), so this
is meant to run on the same box as the stack (manually or via cron), not
against a remote audit endpoint.

KNOWN CAVEAT -- audit's cursor pagination is not reliable across pages.
audit/internal/store/postgres.go's Query() sorts by
`created_at ASC, receipt_id ASC` but paginates with `WHERE receipt_id >
$cursor`, and receipt_id is a random uuid.NewString() (see
audit/internal/service/service.go) with no relationship to created_at.
Once results span more than one page, cursor continuation can silently
skip or duplicate rows -- this is a pre-existing bug in the audit service
itself, not something this script can correct from the outside. To avoid
depending on it in the common case, this script defaults to a large
single-page limit so most windows are fetched in one request; if the
service still hands back a next_cursor (meaning the true row count
exceeded --page-limit), this script prints a warning to stderr because
completeness is no longer guaranteed from that point on. Treat that
warning as a signal to narrow --since/--tenant-id, or as a reason to fix
the cursor to a composite (created_at, receipt_id) keyset in a future
phase.

Usage:
    python3 scripts/asi10-rogue-agent-query.py
    python3 scripts/asi10-rogue-agent-query.py --tenant-id default --since 24h
    python3 scripts/asi10-rogue-agent-query.py --agent-id agent-42 --json

Exit code is 1 if any anomalies were found (so cron can alert on nonzero
exit), 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import requests

EVENT_TYPE_TOOL_GATE = "TOOL_GATE"
DEFAULT_BASE_URL = "http://localhost:8084"
# Large on purpose: audit's cursor pagination is not safe to rely on across
# pages (see the KNOWN CAVEAT in the module docstring), so the default is
# sized to fetch a typical early-stage demo box's whole TOOL_GATE history in
# one request rather than triggering cursor continuation at all.
DEFAULT_PAGE_LIMIT = 5000


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"audit service base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument(
        "--token",
        default=os.environ.get("AEGIS_INTERNAL_TOKEN", ""),
        help="shared internal service token -- audit rejects unauthenticated requests now "
        "(default: read from AEGIS_INTERNAL_TOKEN)",
    )
    parser.add_argument("--tenant-id", default="", help="restrict to one tenant (default: all tenants)")
    parser.add_argument("--agent-id", default="", help="restrict the report to one agent_id (still fetches all, filters client-side)")
    parser.add_argument("--since", default="", help="only consider receipts after this time: ISO-8601 (2026-08-13T00:00:00Z) or relative like 24h / 30m / 7d")
    parser.add_argument("--page-limit", type=int, default=DEFAULT_PAGE_LIMIT, help=f"receipts per page while paginating (default: {DEFAULT_PAGE_LIMIT})")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout per request in seconds (default: 10)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead of a text report")
    return parser.parse_args(argv)


def _parse_since(value: str) -> str | None:
    """Return an ISO-8601 UTC timestamp string, or None if value is empty."""
    if not value:
        return None
    m = re.fullmatch(r"(\d+)([smhd])", value.strip())
    if m:
        amount, unit = int(m.group(1)), m.group(2)
        delta = {
            "s": timedelta(seconds=amount),
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
        }[unit]
        return (datetime.now(timezone.utc) - delta).isoformat()
    # Assume it's already an ISO-8601 timestamp; let the audit service reject it if not.
    return value


def fetch_tool_gate_receipts(
    base_url: str,
    token: str,
    tenant_id: str,
    since_iso: str | None,
    page_limit: int,
    timeout: float,
    session: requests.Session | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield every TOOL_GATE receipt in the window, paginating via cursor.

    See the module docstring's KNOWN CAVEAT: audit's cursor is a random
    UUID with no relationship to the created_at ordering it paginates, so
    if the service ever hands back a next_cursor here, completeness from
    that point on is not guaranteed. We still follow it (best effort is
    better than silently truncating), but warn once so it's visible.
    """
    http = session or requests.Session()
    cursor = ""
    warned = False
    while True:
        params: dict[str, Any] = {"event_type": EVENT_TYPE_TOOL_GATE, "limit": page_limit}
        if tenant_id:
            params["tenant_id"] = tenant_id
        if since_iso:
            params["start_time"] = since_iso
        if cursor:
            params["cursor"] = cursor

        headers = {"Authorization": f"Bearer {token}"}
        resp = http.get(f"{base_url.rstrip('/')}/v1/receipts", params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()

        receipts = body.get("receipts") or []
        for receipt in receipts:
            yield receipt

        cursor = body.get("next_cursor") or ""
        if cursor and not warned:
            print(
                "warning: audit returned a next_cursor -- more TOOL_GATE receipts exist than "
                "--page-limit. audit's cursor pagination is not guaranteed complete/gap-free "
                "(see KNOWN CAVEAT in this script's docstring); consider narrowing --since or "
                "raising --page-limit instead of trusting cursor continuation here.",
                file=sys.stderr,
            )
            warned = True
        if not cursor or not receipts:
            break


def extract_tool_calls(receipts: Iterator[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pull (agent_id, tool_name, created_at, receipt_id, trace_id) out of raw receipts.

    tool_decision is a nested JSON object on each receipt (see
    agent-gate/internal/audit/client.go's toolPayload and the API response
    shape confirmed in audit/internal/models/receipt.go's Receipt struct).
    Receipts missing tool_decision, agent_id, or tool_name are skipped --
    they predate Phase 3.1 (agent_id population) or are otherwise incomplete.
    """
    calls = []
    for r in receipts:
        decision = r.get("tool_decision") or {}
        agent_id = decision.get("agent_id")
        tool_name = decision.get("tool_name")
        if not agent_id or not tool_name:
            continue
        calls.append(
            {
                "agent_id": agent_id,
                "tool_name": tool_name,
                "created_at": r.get("created_at", ""),
                "receipt_id": r.get("receipt_id", ""),
                "trace_id": (r.get("trace") or {}).get("trace_id", ""),
            }
        )
    return calls


def find_first_time_tool_anomalies(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag each agent's first use of a tool outside its established baseline.

    calls must be in chronological order (the audit API already returns
    ORDER BY created_at ASC, receipt_id ASC; we sort defensively here too
    since this is the only place correctness of the whole script hinges on
    ordering).
    """
    ordered = sorted(calls, key=lambda c: (c["created_at"], c["receipt_id"]))
    seen_tools: dict[str, set[str]] = {}
    anomalies = []
    for call in ordered:
        agent_id = call["agent_id"]
        tool_name = call["tool_name"]
        baseline = seen_tools.setdefault(agent_id, set())
        if baseline and tool_name not in baseline:
            anomalies.append({**call, "prior_tool_count": len(baseline)})
        baseline.add(tool_name)
    return anomalies


def _print_text_report(calls: list[dict[str, Any]], anomalies: list[dict[str, Any]], agent_filter: str) -> None:
    agents = {c["agent_id"] for c in calls}
    print("ASI10 rogue-agent tool-use report")
    print(f"  TOOL_GATE receipts scanned: {len(calls)}")
    print(f"  distinct agents seen:       {len(agents)}")
    print(f"  anomalies (new tool for an established agent): {len(anomalies)}")
    print()
    shown = [a for a in anomalies if not agent_filter or a["agent_id"] == agent_filter]
    if not shown:
        print("  (none)" if agent_filter else "  No anomalies found.")
        return
    for a in shown:
        print(
            f"  [{a['created_at']}] agent={a['agent_id']!r} first used tool={a['tool_name']!r} "
            f"(had {a['prior_tool_count']} other distinct tool(s) before this) "
            f"receipt={a['receipt_id']} trace={a['trace_id']}"
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    since_iso = _parse_since(args.since)

    try:
        receipts = fetch_tool_gate_receipts(
            base_url=args.base_url,
            token=args.token,
            tenant_id=args.tenant_id,
            since_iso=since_iso,
            page_limit=args.page_limit,
            timeout=args.timeout,
        )
        calls = extract_tool_calls(receipts)
    except requests.RequestException as exc:
        print(f"error: failed to query audit service at {args.base_url}: {exc}", file=sys.stderr)
        return 2

    anomalies = find_first_time_tool_anomalies(calls)
    if args.agent_id:
        anomalies = [a for a in anomalies if a["agent_id"] == args.agent_id]

    if args.json:
        print(json.dumps({"scanned": len(calls), "anomalies": anomalies}, indent=2))
    else:
        _print_text_report(calls, anomalies, args.agent_id)

    return 1 if anomalies else 0


if __name__ == "__main__":
    raise SystemExit(main())
