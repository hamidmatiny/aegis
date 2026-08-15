"""Deep tests of the governed loop's control flow, against scripted stub
clients -- no network, no real model, no real agent-gate. This is where
this harness's actual security property gets proven: a tool's
`execute()` is unreachable unless the gate decision was ALLOWED.
"""

from __future__ import annotations

import json

import pytest

from aegis_harness.clients import GateDecision
from aegis_harness.errors import ApprovalTimeoutError, TurnBudgetExceededError
from aegis_harness.loop import _execute_after_gate, run_agent
from aegis_harness.tool import Tool, ToolRegistry


class SpyTool(Tool):
    """A tool that records every real execute() call, so tests can
    assert it was never reached when it shouldn't have been."""

    name = "spy_tool"
    description = "records calls for test assertions"
    risk_level = "LOW"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def argument_schema(self) -> dict:
        return {"note": "string"}

    def execute(self, arguments: dict) -> str:
        self.calls.append(arguments)
        return f"executed with {arguments}"


class RaisingTool(Tool):
    name = "raising_tool"
    description = "always raises, to test tool-error handling"
    risk_level = "LOW"

    def argument_schema(self) -> dict:
        return {}

    def execute(self, arguments: dict) -> str:
        raise ValueError("boom")


def _tool_call_response(tool_name: str, arguments: dict | None = None) -> str:
    return json.dumps({"tool_call": {"tool_name": tool_name, "arguments": arguments or {}}})


class ScriptedModelClient:
    """Returns each response in `responses` in order, one per call.
    Raises if asked for more responses than scripted -- a test bug, not
    something the harness itself should ever hit here."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        self.call_count += 1
        if not self._responses:
            raise AssertionError("ScriptedModelClient ran out of scripted responses")
        return self._responses.pop(0)


class ScriptedGateClient:
    """Returns each decision in `decisions` in order for `evaluate()`
    calls, and `approval_decisions` in order for `wait_for_approval()`
    calls -- separate queues since a real run may call one without the
    other."""

    def __init__(
        self,
        decisions: list[GateDecision],
        approval_decisions: list[GateDecision] | None = None,
    ) -> None:
        self._decisions = list(decisions)
        self._approval_decisions = list(approval_decisions or [])
        self.evaluate_calls: list[dict] = []
        self.wait_calls: list[str] = []

    async def evaluate(
        self, *, tool_name, arguments, agent_id, risk_level=""
    ) -> GateDecision:
        self.evaluate_calls.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "agent_id": agent_id,
                "risk_level": risk_level,
            }
        )
        if not self._decisions:
            raise AssertionError("ScriptedGateClient ran out of scripted evaluate() decisions")
        return self._decisions.pop(0)

    async def wait_for_approval(
        self, approval_request_id, *, timeout_seconds, poll_interval_seconds
    ) -> GateDecision:
        self.wait_calls.append(approval_request_id)
        if not self._approval_decisions:
            raise AssertionError("ScriptedGateClient ran out of scripted approval decisions")
        return self._approval_decisions.pop(0)


@pytest.mark.asyncio
async def test_final_answer_on_first_turn_never_touches_gate():
    model = ScriptedModelClient(["The answer is 42."])
    gate = ScriptedGateClient(decisions=[])
    result = await run_agent(
        system_prompt="be helpful",
        user_message="what is the answer?",
        tools=ToolRegistry(),
        model_client=model,
        gate_client=gate,
    )
    assert result.final_answer == "The answer is 42."
    assert result.turns_used == 1
    assert gate.evaluate_calls == []


@pytest.mark.asyncio
async def test_allowed_tool_call_executes_and_result_feeds_back():
    tool = SpyTool()
    registry = ToolRegistry()
    registry.register(tool)

    model = ScriptedModelClient(
        [
            _tool_call_response("spy_tool", {"note": "hi"}),
            "Done, the tool ran.",
        ]
    )
    gate = ScriptedGateClient(decisions=[GateDecision(status="APPROVED")])

    result = await run_agent(
        system_prompt="be helpful",
        user_message="use the spy tool",
        tools=registry,
        model_client=model,
        gate_client=gate,
    )

    assert result.final_answer == "Done, the tool ran."
    assert tool.calls == [{"note": "hi"}]
    assert [t.kind for t in result.transcript] == [
        "tool_call_requested",
        "tool_result",
        "final_answer",
    ]


@pytest.mark.asyncio
async def test_denied_tool_call_never_reaches_execute():
    tool = SpyTool()
    registry = ToolRegistry()
    registry.register(tool)

    model = ScriptedModelClient(
        [
            _tool_call_response("spy_tool", {"note": "should not run"}),
            "Okay, I won't do that.",
        ]
    )
    gate = ScriptedGateClient(
        decisions=[GateDecision(status="DENIED", denial_reason="blocked by policy")]
    )

    result = await run_agent(
        system_prompt="be helpful",
        user_message="try the spy tool",
        tools=registry,
        model_client=model,
        gate_client=gate,
    )

    assert tool.calls == []  # the actual security property this whole package exists for
    assert result.final_answer == "Okay, I won't do that."
    assert [t.kind for t in result.transcript] == ["tool_call_requested", "denied", "final_answer"]


@pytest.mark.asyncio
async def test_awaiting_approval_then_approved_executes_after_wait():
    tool = SpyTool()
    registry = ToolRegistry()
    registry.register(tool)

    model = ScriptedModelClient(
        [
            _tool_call_response("spy_tool", {"note": "irreversible-ish"}),
            "Approved and done.",
        ]
    )
    gate = ScriptedGateClient(
        decisions=[GateDecision(status="AWAITING_HUMAN_APPROVAL", approval_request_id="appr-1")],
        approval_decisions=[GateDecision(status="APPROVED", approval_request_id="appr-1")],
    )

    result = await run_agent(
        system_prompt="be helpful",
        user_message="try the spy tool",
        tools=registry,
        model_client=model,
        gate_client=gate,
    )

    assert tool.calls == [{"note": "irreversible-ish"}]  # only after the wait resolved to APPROVED
    assert gate.wait_calls == ["appr-1"]
    assert [t.kind for t in result.transcript] == [
        "tool_call_requested",
        "awaiting_approval",
        "tool_result",
        "final_answer",
    ]


@pytest.mark.asyncio
async def test_awaiting_approval_then_denied_never_reaches_execute():
    tool = SpyTool()
    registry = ToolRegistry()
    registry.register(tool)

    model = ScriptedModelClient(
        [
            _tool_call_response("spy_tool"),
            "Understood, denied.",
        ]
    )
    gate = ScriptedGateClient(
        decisions=[GateDecision(status="AWAITING_HUMAN_APPROVAL", approval_request_id="appr-2")],
        approval_decisions=[GateDecision(status="DENIED", approval_request_id="appr-2")],
    )

    result = await run_agent(
        system_prompt="be helpful",
        user_message="try the spy tool",
        tools=registry,
        model_client=model,
        gate_client=gate,
    )

    assert tool.calls == []
    assert result.final_answer == "Understood, denied."


@pytest.mark.asyncio
async def test_approval_timeout_raises_and_never_executes():
    tool = SpyTool()
    registry = ToolRegistry()
    registry.register(tool)

    model = ScriptedModelClient([_tool_call_response("spy_tool")])
    gate = ScriptedGateClient(
        decisions=[GateDecision(status="AWAITING_HUMAN_APPROVAL", approval_request_id="appr-3")],
        approval_decisions=[GateDecision(status="TIMED_OUT", approval_request_id="appr-3")],
    )

    with pytest.raises(ApprovalTimeoutError):
        await run_agent(
            system_prompt="be helpful",
            user_message="try the spy tool",
            tools=registry,
            model_client=model,
            gate_client=gate,
            approval_timeout_seconds=0.01,
            approval_poll_interval_seconds=0.001,
        )

    assert tool.calls == []


@pytest.mark.asyncio
async def test_unknown_tool_does_not_crash_and_never_calls_gate():
    registry = ToolRegistry()  # deliberately empty
    model = ScriptedModelClient(
        [
            _tool_call_response("does_not_exist"),
            "My mistake, here's a direct answer instead.",
        ]
    )
    gate = ScriptedGateClient(decisions=[])

    result = await run_agent(
        system_prompt="be helpful",
        user_message="try a tool that doesn't exist",
        tools=registry,
        model_client=model,
        gate_client=gate,
    )

    assert result.final_answer == "My mistake, here's a direct answer instead."
    assert gate.evaluate_calls == []  # never submitted for evaluation -- there was nothing to run
    assert [t.kind for t in result.transcript] == [
        "tool_call_requested",
        "unknown_tool",
        "final_answer",
    ]


@pytest.mark.asyncio
async def test_tool_execution_error_is_caught_and_fed_back():
    tool = RaisingTool()
    registry = ToolRegistry()
    registry.register(tool)

    model = ScriptedModelClient(
        [
            _tool_call_response("raising_tool"),
            "It failed, giving up gracefully.",
        ]
    )
    gate = ScriptedGateClient(decisions=[GateDecision(status="APPROVED")])

    result = await run_agent(
        system_prompt="be helpful",
        user_message="use the raising tool",
        tools=registry,
        model_client=model,
        gate_client=gate,
    )

    assert result.final_answer == "It failed, giving up gracefully."
    assert [t.kind for t in result.transcript] == [
        "tool_call_requested",
        "tool_error",
        "final_answer",
    ]


@pytest.mark.asyncio
async def test_turn_budget_exceeded_raises():
    tool = SpyTool()
    registry = ToolRegistry()
    registry.register(tool)

    # The model just keeps calling the tool forever and never answers.
    model = ScriptedModelClient([_tool_call_response("spy_tool")] * 5)
    gate = ScriptedGateClient(decisions=[GateDecision(status="APPROVED")] * 5)

    with pytest.raises(TurnBudgetExceededError):
        await run_agent(
            system_prompt="be helpful",
            user_message="loop forever",
            tools=registry,
            model_client=model,
            gate_client=gate,
            max_turns=3,
        )
    # tool did run 3 times (each was genuinely ALLOWED) -- the budget cap
    # is what stops the run, not a governance failure
    assert len(tool.calls) == 3


def test_execute_after_gate_refuses_without_allowed_decision_even_called_directly():
    """The last line of defense, tested in isolation from run_agent's own
    branching -- proves the guard holds even if a future refactor of the
    loop ever called this helper incorrectly."""
    tool = SpyTool()
    with pytest.raises(RuntimeError):
        _execute_after_gate(tool, {}, GateDecision(status="DENIED"))
    with pytest.raises(RuntimeError):
        _execute_after_gate(tool, {}, GateDecision(status="AWAITING_HUMAN_APPROVAL"))
    assert tool.calls == []


def test_execute_after_gate_runs_tool_when_allowed():
    tool = SpyTool()
    result = _execute_after_gate(tool, {"note": "ok"}, GateDecision(status="APPROVED"))
    assert result == "executed with {'note': 'ok'}"
    assert tool.calls == [{"note": "ok"}]
