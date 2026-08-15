"""CLI entry point for the harness -- a thin wrapper around `run_agent`.

Kept deliberately thin: everything this script does is call the public
`run_agent` function with real HTTP clients. A future HTTP service
wrapping the same loop would look the same way -- construct the same
clients, call the same function, serialize the same `AgentRunResult` --
which is the whole point of keeping loop.py's core function pure and
this file separate from it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from aegis_harness.clients import AgentGateClient, ModelRouterClient
from aegis_harness.errors import ApprovalTimeoutError, HarnessError, TurnBudgetExceededError
from aegis_harness.loop import run_agent
from aegis_harness.tools import default_tool_registry

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a small set of tools. "
    "Use them when they genuinely help answer the user's request; "
    "otherwise just answer directly."
)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


async def _main_async(args: argparse.Namespace) -> int:
    model_client = ModelRouterClient(
        base_url=_env("AEGIS_MODEL_ROUTER_URL", "http://localhost:8082"),
        internal_token=_env("AEGIS_INTERNAL_TOKEN"),
    )
    gate_client = AgentGateClient(
        base_url=_env("AEGIS_AGENT_GATE_URL", "http://localhost:8083"),
        service_api_key=_env("AEGIS_AGENT_GATE_API_KEYS").split(",")[0].strip(),
        tenant_id=args.tenant_id,
    )

    try:
        result = await run_agent(
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            user_message=args.message,
            tools=default_tool_registry(),
            model_client=model_client,
            gate_client=gate_client,
            model=args.model,
            agent_id=args.agent_id,
            max_turns=args.max_turns,
            approval_timeout_seconds=args.approval_timeout,
        )
    except TurnBudgetExceededError as exc:
        print(f"RUN INCOMPLETE: {exc}", file=sys.stderr)
        return 1
    except ApprovalTimeoutError as exc:
        print(f"RUN PAUSED (approval not decided in time): {exc}", file=sys.stderr)
        return 2
    except HarnessError as exc:
        print(f"RUN FAILED: {exc}", file=sys.stderr)
        return 1

    print("--- transcript ---")
    for turn in result.transcript:
        line = f"[{turn.kind}]"
        if turn.tool_name:
            line += f" tool={turn.tool_name}"
        if turn.approval_request_id:
            line += f" approval_id={turn.approval_request_id}"
        if turn.detail:
            line += f" -- {turn.detail}"
        print(line)
    print("--- final answer ---")
    print(result.final_answer)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a governed AEGIS harness agent loop (Stage: operator-platform phase 1)."
    )
    parser.add_argument("message", help="the user message / task to give the agent")
    parser.add_argument("--model", default="mock-model")
    parser.add_argument("--agent-id", default="aegis-harness-cli")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--approval-timeout", type=float, default=300.0)
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
