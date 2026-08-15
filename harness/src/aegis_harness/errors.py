"""Exception types raised by the AEGIS harness loop."""

from __future__ import annotations


class HarnessError(Exception):
    """Base class for all harness-raised errors."""


class UnknownToolError(HarnessError):
    """The model asked for a tool that isn't in the registry. Never a
    reason to crash the run -- the loop catches this and feeds an error
    back to the model so it can try something registered instead."""


class TurnBudgetExceededError(HarnessError):
    """The loop hit its max_turns cap without the model returning a
    final answer. A deliberate safety bound, not a bug -- see
    loop.py's `max_turns` parameter."""


class ApprovalTimeoutError(HarnessError):
    """A tool call was escalated to AWAITING_HUMAN_APPROVAL and no
    reviewer decided it within `approval_timeout_seconds`. The run stops
    here rather than looping forever on a poll -- the approval itself is
    still live in agent-gate and can be decided later out-of-band."""


class ToolExecutionError(HarnessError):
    """A tool's own `execute()` raised. Wraps the original exception so
    the loop can feed a safe, generic error message back to the model
    without necessarily leaking internal exception details into a
    model-visible transcript."""

    def __init__(self, tool_name: str, original: Exception) -> None:
        super().__init__(f"tool '{tool_name}' failed: {original}")
        self.tool_name = tool_name
        self.original = original
