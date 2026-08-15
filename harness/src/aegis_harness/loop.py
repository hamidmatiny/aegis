"""The governed agent loop -- the actual point of this whole package.

`run_agent` is a plain importable async function, not a class with
hidden state and not an HTTP handler. That split is deliberate: wrapping
this in a CLI (see cli.py) or, later, an HTTP service is additive either
way, since nothing about the core loop's call signature or behavior
needs to change to support either invocation style.

The one property this whole harness exists to demonstrate: a tool's
`execute()` is only ever reachable through `_execute_after_gate`, and
`_execute_after_gate` refuses to run without an ALLOWED `GateDecision`.
That is a code-level guarantee, not a convention the loop happens to
follow -- there is exactly one call site for `tool.execute()` in this
entire module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from aegis_harness.clients import GateClient, GateDecision, ModelClient
from aegis_harness.errors import (
    ApprovalTimeoutError,
    ToolExecutionError,
    TurnBudgetExceededError,
)
from aegis_harness.protocol import build_system_prompt, parse_model_response
from aegis_harness.tool import Tool, ToolRegistry

TurnKind = Literal[
    "tool_call_requested",
    "awaiting_approval",
    "denied",
    "unknown_tool",
    "tool_result",
    "tool_error",
    "final_answer",
]


@dataclass
class Turn:
    """One step of the run's transcript, kept for observability and
    debugging -- not sent back to the model (loop.py builds its own
    `messages` history separately). Mirrors this project's
    audit-everything ethos: every governance-relevant event in a run is
    represented here, not just the final answer."""

    kind: TurnKind
    tool_name: str | None = None
    detail: str | None = None
    approval_request_id: str | None = None


@dataclass
class AgentRunResult:
    final_answer: str
    transcript: list[Turn] = field(default_factory=list)
    turns_used: int = 0


async def run_agent(
    *,
    system_prompt: str,
    user_message: str,
    tools: ToolRegistry,
    model_client: ModelClient,
    gate_client: GateClient,
    model: str = "mock-model",
    provider: str = "",
    agent_id: str = "aegis-harness",
    max_turns: int = 8,
    approval_timeout_seconds: float = 300.0,
    approval_poll_interval_seconds: float = 2.0,
) -> AgentRunResult:
    """Run a bounded, governed agent loop to completion.

    Every tool call the model requests is submitted to `gate_client`
    (agent-gate, in real use) before it can run. An IRREVERSIBLE-risk
    tool call that gets escalated to human approval blocks this call
    until a reviewer decides it or `approval_timeout_seconds` elapses --
    there is no code path here that proceeds to execute a tool while an
    approval is still pending.

    Raises `TurnBudgetExceededError` if the model never returns a final
    answer within `max_turns`, and `ApprovalTimeoutError` if a pending
    approval isn't decided in time. Both are real termination conditions
    a caller should expect and handle, not edge cases to ignore.

    `provider` is forwarded to `model_client.complete()` unchanged on
    every turn -- left empty (the default), model-router falls back to
    its own configured default provider ("mock"), which is why every
    prior run of this harness only ever talked to the mock echo. Set it
    to "openai"/"anthropic"/"gemini"/"grok"/"ollama"/"vllm" to run
    against a real model; see harness/README.md.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(tools, system_prompt)},
        {"role": "user", "content": user_message},
    ]
    transcript: list[Turn] = []

    for turn_index in range(max_turns):
        response_text = await model_client.complete(
            model=model, messages=messages, provider=provider
        )
        parsed = parse_model_response(response_text)

        if parsed.final_answer is not None:
            transcript.append(Turn(kind="final_answer", detail=parsed.final_answer))
            return AgentRunResult(
                final_answer=parsed.final_answer,
                transcript=transcript,
                turns_used=turn_index + 1,
            )

        assert parsed.tool_call is not None  # parse_model_response's own invariant
        call = parsed.tool_call
        messages.append({"role": "assistant", "content": response_text})
        transcript.append(Turn(kind="tool_call_requested", tool_name=call.tool_name))

        tool = tools.get(call.tool_name)
        if tool is None:
            transcript.append(Turn(kind="unknown_tool", tool_name=call.tool_name))
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Tool result: error, unknown tool '{call.tool_name}'. "
                        f"Available tools: {', '.join(tools.names())}"
                    ),
                }
            )
            continue

        decision = await gate_client.evaluate(
            tool_name=tool.name,
            arguments=call.arguments,
            agent_id=agent_id,
            risk_level=tool.risk_level,
        )

        if decision.awaiting_approval:
            transcript.append(
                Turn(
                    kind="awaiting_approval",
                    tool_name=tool.name,
                    approval_request_id=decision.approval_request_id,
                )
            )
            assert decision.approval_request_id is not None
            decision = await gate_client.wait_for_approval(
                decision.approval_request_id,
                timeout_seconds=approval_timeout_seconds,
                poll_interval_seconds=approval_poll_interval_seconds,
            )
            if decision.status == "TIMED_OUT":
                raise ApprovalTimeoutError(
                    f"tool '{tool.name}' (approval {call.tool_name!r}) was not decided "
                    f"within {approval_timeout_seconds}s"
                )

        if not decision.allowed:
            transcript.append(
                Turn(kind="denied", tool_name=tool.name, detail=decision.denial_reason)
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Tool result: denied -- {decision.denial_reason or 'denied by policy'}"
                    ),
                }
            )
            continue

        try:
            result_text = _execute_after_gate(tool, call.arguments, decision)
        except ToolExecutionError as exc:
            transcript.append(Turn(kind="tool_error", tool_name=tool.name, detail=str(exc)))
            messages.append({"role": "user", "content": f"Tool result: error -- {exc}"})
            continue

        transcript.append(Turn(kind="tool_result", tool_name=tool.name, detail=result_text))
        messages.append({"role": "user", "content": f"Tool result: {result_text}"})

    raise TurnBudgetExceededError(f"no final answer within {max_turns} turns")


def _execute_after_gate(tool: Tool, arguments: dict[str, Any], decision: GateDecision) -> str:
    """The single call site for `tool.execute()` in this entire package.

    The `decision.allowed` check below is intentionally redundant with
    the caller's own branch in `run_agent` -- if a future refactor of
    `run_agent` ever calls this without checking first, this is the line
    that still stops it, not a comment asking someone to remember to."""
    if not decision.allowed:
        raise RuntimeError(
            "internal error: _execute_after_gate called without an ALLOWED decision -- "
            "this should be unreachable, please report it as a bug"
        )
    try:
        return tool.execute(arguments)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see ToolExecutionError
        raise ToolExecutionError(tool.name, exc) from exc
