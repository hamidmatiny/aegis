from __future__ import annotations

import json

from aegis_harness.protocol import build_system_prompt, parse_model_response
from aegis_harness.tool import Tool, ToolRegistry


class _FakeTool(Tool):
    name = "fake_tool"
    description = "a fake tool for prompt-building tests"
    risk_level = "MEDIUM"

    def argument_schema(self) -> dict:
        return {"x": "string"}

    def execute(self, arguments: dict) -> str:
        return "ok"


def test_build_system_prompt_lists_tools_and_schema():
    registry = ToolRegistry()
    registry.register(_FakeTool())
    prompt = build_system_prompt(registry, "base instructions")
    assert "base instructions" in prompt
    assert "fake_tool" in prompt
    assert "MEDIUM" in prompt
    assert '"x":"string"' in prompt or '"x": "string"' in prompt
    assert "tool_call" in prompt


def test_build_system_prompt_empty_registry_returns_base_unchanged():
    prompt = build_system_prompt(ToolRegistry(), "just the base prompt")
    assert prompt == "just the base prompt"


def test_parse_plain_json_tool_call():
    text = json.dumps({"tool_call": {"tool_name": "search_docs", "arguments": {"query": "x"}}})
    parsed = parse_model_response(text)
    assert parsed.tool_call is not None
    assert parsed.final_answer is None
    assert parsed.tool_call.tool_name == "search_docs"
    assert parsed.tool_call.arguments == {"query": "x"}


def test_parse_fenced_json_tool_call():
    text = (
        "Sure, I'll do that:\n"
        "```json\n"
        '{"tool_call": {"tool_name": "send_email", "arguments": {"to": "a@b.com"}}}\n'
        "```"
    )
    parsed = parse_model_response(text)
    assert parsed.tool_call is not None
    assert parsed.tool_call.tool_name == "send_email"
    assert parsed.tool_call.arguments == {"to": "a@b.com"}


def test_parse_plain_prose_is_final_answer():
    parsed = parse_model_response("The capital of France is Paris.")
    assert parsed.final_answer == "The capital of France is Paris."
    assert parsed.tool_call is None


def test_parse_malformed_json_fails_open_to_final_answer():
    # A model that garbled the tool_call format shouldn't crash the loop
    # or be guessed-at -- treated as a (weird) final answer instead.
    parsed = parse_model_response('{"tool_call": {"tool_name": }}')
    assert parsed.final_answer is not None
    assert parsed.tool_call is None


def test_parse_json_without_tool_call_key_is_final_answer():
    parsed = parse_model_response(json.dumps({"answer": "42"}))
    assert parsed.final_answer is not None
    assert parsed.tool_call is None


def test_parse_tool_call_missing_tool_name_is_final_answer():
    parsed = parse_model_response(json.dumps({"tool_call": {"arguments": {}}}))
    assert parsed.tool_call is None
    assert parsed.final_answer is not None
