#!/usr/bin/env python3
"""One-shot real-LLM verification for all 12 corp agents.

Requires a working XAI_API_KEY in model-router (CORP_FORCE_MOCK_LLM=false).
Does not enable the recurring scheduler.

Usage:
  CORP_FORCE_MOCK_LLM=false CORP_SCHEDULER_ENABLED=false \\
    docker compose up -d --force-recreate --no-deps corp-orchestrator
  python corp-orchestrator/scripts/verify_real_llm_agents.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

CORP = os.environ.get("CORP_ORCHESTRATOR_URL", "http://127.0.0.1:8094").rstrip("/")
TOKEN = os.environ.get("AEGIS_INTERNAL_TOKEN") or ""


def http(method: str, path: str, body: dict | None = None, timeout: float = 300) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        CORP + path,
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    if not TOKEN:
        print("AEGIS_INTERNAL_TOKEN required", file=sys.stderr)
        return 2
    agents = http("GET", "/v1/agents")["agents"]
    print(f"agents={len(agents)}")
    results = []
    ok = True
    for a in agents:
        dept, team = a["department"], a["team"]
        print(f"\n>>> {dept}/{team} ({a['model_provider']}/{a['model_name']})", flush=True)
        t0 = time.time()
        try:
            out = http("POST", "/v1/tasks/run", {"department": dept, "team": team})
        except urllib.error.HTTPError as exc:
            out = {"error": exc.read().decode(), "status": "http_error"}
            ok = False
        except Exception as exc:  # noqa: BLE001
            out = {"error": str(exc), "status": "error"}
            ok = False
        elapsed = round(time.time() - t0, 1)
        row = {
            "department": dept,
            "team": team,
            "provider": out.get("provider"),
            "model": out.get("model"),
            "status": out.get("status") or out.get("error"),
            "elapsed_s": elapsed,
            "pending_tool": (out.get("pending_approval") or {}).get("tool_name"),
            "result_head": (out.get("result") or out.get("error") or "")[:600],
            "task_id": out.get("task_id"),
        }
        if row["provider"] in (None, "mock") or row["model"] in (None, "mock-model"):
            print("FAIL: expected real provider/model, got", row["provider"], row["model"])
            ok = False
        if row["status"] == "failed":
            print("FAIL: task failed —", str(row["result_head"])[:200])
            ok = False
        if row["status"] == "failed" and "401" in str(row["result_head"]):
            print("FAIL: model-router auth/provider key error — fix XAI_API_KEY")
            ok = False
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    out_path = os.environ.get("CORP_REAL_LLM_OUT", "/tmp/corp-real-llm-results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {out_path}")
    for r in results:
        print(
            f"{r['department']}/{r['team']}: {r['status']} "
            f"{r['provider']}/{r['model']} pending={r['pending_tool']} t={r['elapsed_s']}s"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
