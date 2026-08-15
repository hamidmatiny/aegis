#!/usr/bin/env python3
"""Flag inter-agent identity inconsistencies (OWASP ASI07) from audit's
TOOL_GATE receipts.

The real gap this closes: agent-gate's tool-call `agent_id` is entirely
caller-declared and never verified against the credential that actually
authenticated the request (agent-gate's auth is a shared service-key set
-- see agent-gate/internal/auth/auth.go -- with no per-agent binding). Any
caller holding a valid service key can claim to be any agent_id,
including one that isn't theirs. That undermines both the audit trail's
attribution and scripts/asi10-rogue-agent-query.py's own baselining,
which assumes agent_id reliably identifies one calling agent over time.

Stage E.2 added `service_key_fingerprint` to every TOOL_GATE receipt (see
agent-gate/internal/auth/auth.go's Fingerprint() and
agent-gate/internal/audit/client.go's EmitToolGate) -- a short,
non-reversible hash of whichever service key authenticated the request.
This script cross-checks agent_id claims against that fingerprint:

1. Per-agent fingerprint anomalies (the higher-confidence signal): for
   each agent_id, track the set of fingerprints already seen. Once an
   agent_id has an established baseline (at least one prior fingerprint),
   any call under a NEW fingerprint is flagged -- the same "first time
   outside the baseline" pattern as asi10-rogue-agent-query.py's
   first-time-tool detection, just keyed by identity instead of
   capability. A legitimate credential rotation looks exactly like this
   too, so a flag here means "investigate," not "confirmed attack."

2. Per-fingerprint agent cardinality (informational by default): how
   many distinct agent_id values each fingerprint has claimed. This is
   NOT flagged as an anomaly unless --max-agents-per-key is set, because
   this repo's own examples and integration tests legitimately share one
   configured key across several agent_id values out of the box --
   AEGIS's shared-key model doesn't distinguish "one key, one real agent"
   from "one key, deliberately shared across an agent fleet" the way
   real per-agent credentials would. Set --max-agents-per-key if your own
   deployment provisions one key per agent and wants that assumption
   enforced.

This is a DETECTION signal, not a new authorization check -- agent-gate
does not block on any of this. True per-agent enforcement would need
real per-agent credentials (a bigger architecture change than this
phase), which this script deliberately does not attempt to fake.

Usage:
    python3 scripts/asi07-identity-consistency-query.py
    python3 scripts/asi07-identity-consistency-query.py --tenant-id default --since 24h
    python3 scripts/asi07-identity-consistency-query.py --max-agents-per-key 3 --json

Exit code is 1 if any fingerprint anomalies were found (so cron can alert
on nonzero exit), or if --max-agents-per-key is set and exceeded. 0
otherwise.
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
# Same rationale as asi10-rogue-agent-query.py's identical default: large
# enough to fetch a typical early-stage demo box's whole TOOL_GATE history
# in one request; multi-page cursor continuation is reliable (Stage B.3)
# if a window ever needs more than one page.
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
    parser.add_argument("--agent-id", default="", help="restrict the anomaly report to one agent_id (still fetches all, filters client-side)")
    parser.add_argument("--since", default="", help="only consider receipts after this time: ISO-8601 (2026-08-13T00:00:00Z) or relative like 24h / 30m / 7d")
    parser.add_argument("--page-limit", type=int, default=DEFAULT_PAGE_LIMIT, help=f"receipts per page while paginating (default: {DEFAULT_PAGE_LIMIT})")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout per request in seconds (default: 10)")
    parser.add_argument(
        "--max-agents-per-key",
        type=int,
        default=0,
        help="if set (>0), also flag any service_key_fingerprint that has claimed more than this many "
        "distinct agent_id values as an anomaly. Unset (default) means this signal is informational only.",
    )
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

    Identical logic to asi10-rogue-agent-query.py's function of the same
    name -- duplicated rather than shared, matching this repo's existing
    scripts/ convention of self-contained, standalone scripts (no shared
    lib module exists for this directory).
    """
    http = session or requests.Session()
    cursor = ""
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
        if not cursor or not receipts:
            break


def extract_identity_calls(receipts: Iterator[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pull (agent_id, service_key_fingerprint, created_at, receipt_id, trace_id)
    out of raw receipts.

    Receipts missing tool_decision, agent_id, or service_key_fingerprint
    are skipped -- they predate Stage E.2 (or Phase 3.1's agent_id
    population), or are otherwise incomplete.
    """
    calls = []
    for r in receipts:
        decision = r.get("tool_decision") or {}
        agent_id = decision.get("agent_id")
        fingerprint = decision.get("service_key_fingerprint")
        if not agent_id or not fingerprint:
            continue
        calls.append(
            {
                "agent_id": agent_id,
                "service_key_fingerprint": fingerprint,
                "created_at": r.get("created_at", ""),
                "receipt_id": r.get("receipt_id", ""),
                "trace_id": (r.get("trace") or {}).get("trace_id", ""),
            }
        )
    return calls


def find_fingerprint_anomalies(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag each agent_id's first use of a fingerprint outside its
    established baseline -- mirrors
    asi10-rogue-agent-query.py's find_first_time_tool_anomalies exactly,
    keyed by identity instead of capability.

    calls must be in chronological order (the audit API already returns
    ORDER BY created_at ASC, receipt_id ASC; we sort defensively here too,
    same as the ASI10 script).
    """
    ordered = sorted(calls, key=lambda c: (c["created_at"], c["receipt_id"]))
    seen_fingerprints: dict[str, set[str]] = {}
    anomalies = []
    for call in ordered:
        agent_id = call["agent_id"]
        fingerprint = call["service_key_fingerprint"]
        baseline = seen_fingerprints.setdefault(agent_id, set())
        if baseline and fingerprint not in baseline:
            anomalies.append({**call, "prior_fingerprint_count": len(baseline)})
        baseline.add(fingerprint)
    return anomalies


def summarize_agents_per_fingerprint(calls: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Return {fingerprint: {agent_id, ...}} -- the cardinality report.
    Informational by default; see --max-agents-per-key."""
    by_fingerprint: dict[str, set[str]] = {}
    for call in calls:
        by_fingerprint.setdefault(call["service_key_fingerprint"], set()).add(call["agent_id"])
    return by_fingerprint


def find_key_cardinality_anomalies(
    by_fingerprint: dict[str, set[str]], max_agents_per_key: int
) -> list[dict[str, Any]]:
    """Only called when --max-agents-per-key > 0 -- see the module
    docstring for why this isn't flagged by default."""
    if max_agents_per_key <= 0:
        return []
    anomalies = []
    for fingerprint, agents in by_fingerprint.items():
        if len(agents) > max_agents_per_key:
            anomalies.append(
                {
                    "service_key_fingerprint": fingerprint,
                    "agent_count": len(agents),
                    "agent_ids": sorted(agents),
                }
            )
    return anomalies


def _print_text_report(
    calls: list[dict[str, Any]],
    fingerprint_anomalies: list[dict[str, Any]],
    by_fingerprint: dict[str, set[str]],
    key_anomalies: list[dict[str, Any]],
    agent_filter: str,
) -> None:
    agents = {c["agent_id"] for c in calls}
    print("ASI07 identity-consistency report")
    print(f"  TOOL_GATE receipts scanned:         {len(calls)}")
    print(f"  distinct agents seen:               {len(agents)}")
    print(f"  distinct service key fingerprints:  {len(by_fingerprint)}")
    print(f"  fingerprint anomalies (new key for an established agent_id): {len(fingerprint_anomalies)}")
    print()
    shown = [a for a in fingerprint_anomalies if not agent_filter or a["agent_id"] == agent_filter]
    if not shown:
        print("  (none)" if agent_filter else "  No fingerprint anomalies found.")
    else:
        for a in shown:
            print(
                f"  [{a['created_at']}] agent_id={a['agent_id']!r} used a NEW key "
                f"(fingerprint={a['service_key_fingerprint']}, had {a['prior_fingerprint_count']} other "
                f"key(s) before this) receipt={a['receipt_id']} trace={a['trace_id']}"
            )
            print(
                "    -> investigate: could be a legitimate credential rotation, or a different"
                " caller claiming this agent_id."
            )
    print()
    print("  agents per key (informational" + ("" if not key_anomalies else f", {len(key_anomalies)} exceed --max-agents-per-key") + "):")
    for fingerprint, agent_ids in sorted(by_fingerprint.items(), key=lambda kv: -len(kv[1])):
        print(f"    {fingerprint}: {len(agent_ids)} agent(s) -- {sorted(agent_ids)}")


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
        calls = extract_identity_calls(receipts)
    except requests.RequestException as exc:
        print(f"error: failed to query audit service at {args.base_url}: {exc}", file=sys.stderr)
        return 2

    fingerprint_anomalies = find_fingerprint_anomalies(calls)
    if args.agent_id:
        fingerprint_anomalies = [a for a in fingerprint_anomalies if a["agent_id"] == args.agent_id]

    by_fingerprint = summarize_agents_per_fingerprint(calls)
    key_anomalies = find_key_cardinality_anomalies(by_fingerprint, args.max_agents_per_key)

    if args.json:
        print(
            json.dumps(
                {
                    "scanned": len(calls),
                    "fingerprint_anomalies": fingerprint_anomalies,
                    "agents_per_key": {fp: sorted(agents) for fp, agents in by_fingerprint.items()},
                    "key_cardinality_anomalies": key_anomalies,
                },
                indent=2,
            )
        )
    else:
        _print_text_report(calls, fingerprint_anomalies, by_fingerprint, key_anomalies, args.agent_id)

    return 1 if (fingerprint_anomalies or key_anomalies) else 0


if __name__ == "__main__":
    raise SystemExit(main())
