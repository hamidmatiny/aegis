"""The prompted tool-calling convention this harness uses.

model-router (see model-router/internal/models/types.go's ChatRequest/
ChatResponse) is a plain provider-agnostic text completion API -- it has
no `tools`/`tool_choice`/`tool_calls` fields, and none of its providers
(including the mock one used for local dev/CI) implement OpenAI-style
native function-calling. Extending model-router itself to add that is a
real, separate change to a shared core service, out of scope for this
harness -- flagged as a natural follow-up, not silently worked around.

Until then, this module implements the older, still-effective pattern
those native APIs formalized: the system prompt describes the available
tools and asks the model to respond with a specific JSON shape to call
one, or plain text for a final answer. `parse_model_response` is
deliberately tolerant of a model wrapping that JSON in prose or a code
fence, since not every model follows formatting instructions exactly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from aegis_harness.tool import ToolRegistry

_TOOL_CALL_KEY = "tool_call"
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def build_system_prompt(registry: ToolRegistry, base_prompt: str) -> str:
    """Compose the operator-provided base system prompt with the tool
    catalog and the response-format instructions the model must follow
    to call one. Called once per run in loop.py, not per turn -- the
    tool list doesn't change mid-run."""
    if len(registry) == 0:
        return base_prompt

    tool_lines = []
    for tool in registry:
        schema = json.dumps(tool.argument_schema(), separators=(",", ":"))
        tool_lines.append(
            f'- {tool.name} ({tool.risk_level} risk): {tool.description}\n'
            f'  arguments schema: {schema}'
        )

    tools_block = "\n".join(tool_lines)
    return (
        f"{base_prompt}\n\n"
        "You have access to the following tools:\n"
        f"{tools_block}\n\n"
        "To call a tool, respond with ONLY a single JSON object of this "
        'exact shape and nothing else:\n'
        '{"tool_call": {"tool_name": "<name>", "arguments": {...}}}\n\n'
        "Every tool call is reviewed by a real, code-level policy engine "
        "before it runs -- some tools require human approval and the "
        "call will pause until a reviewer decides it, some are denied "
        "outright, so don't assume a call you make will execute "
        "immediately or at all. If you are not calling a tool, respond "
        "with your final answer as plain text instead -- do not use the "
        "tool_call JSON shape for anything other than an actual tool call."
    )


@dataclass
class ParsedToolCall:
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ParsedResponse:
    """Exactly one of `tool_call` or `final_answer` is set."""

    tool_call: ParsedToolCall | None = None
    final_answer: str | None = None


def parse_model_response(text: str) -> ParsedResponse:
    """Decide whether the model's raw text response is a tool call or a
    final answer. Tries, in order: the whole trimmed response as JSON,
    a JSON object inside a ```-fenced block, then falls back to treating
    the entire response as the final answer -- a model that didn't
    follow the tool_call format is far more likely to just be answering
    in prose than to have produced malformed tool-call JSON, so failing
    open to "final answer" here is the safer default (the alternative --
    guessing it meant to call a tool and picking one -- is worse)."""
    stripped = text.strip()

    candidate = _try_parse_tool_call(stripped)
    if candidate is not None:
        return ParsedResponse(tool_call=candidate)

    fence_match = _JSON_FENCE_RE.search(stripped)
    if fence_match:
        candidate = _try_parse_tool_call(fence_match.group(1))
        if candidate is not None:
            return ParsedResponse(tool_call=candidate)

    return ParsedResponse(final_answer=stripped)


def _try_parse_tool_call(raw: str) -> ParsedToolCall | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or _TOOL_CALL_KEY not in data:
        return None
    call = data[_TOOL_CALL_KEY]
    if not isinstance(call, dict):
        return None
    tool_name = call.get("tool_name")
    arguments = call.get("arguments", {})
    if not isinstance(tool_name, str) or not tool_name:
        return None
    if not isinstance(arguments, dict):
        return None
    return ParsedToolCall(tool_name=tool_name, arguments=arguments)
