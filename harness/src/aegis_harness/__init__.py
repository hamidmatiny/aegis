"""AEGIS harness -- a minimal, governed multi-step agent loop.

Operator-platform phase 1 (see project memory node N47/N63): the first
concrete piece of "runtime holding it together" from the model layer
(model-router) + harness + tools/skills library + runtime vision. Not a
general-purpose agent framework -- a small, real demonstration that
AEGIS's own governance (agent-gate + policy-engine) can be load-bearing
for an actual multi-step loop, not just advisory for a well-behaved
external caller.

Public API:
    run_agent          -- the core governed loop (aegis_harness.loop)
    Tool, ToolRegistry  -- the extensibility point for adding tools (aegis_harness.tool)
    default_tool_registry -- the three starter tools (aegis_harness.tools)
"""

from __future__ import annotations

from aegis_harness.loop import AgentRunResult, Turn, run_agent
from aegis_harness.tool import Tool, ToolRegistry

__all__ = [
    "AgentRunResult",
    "Tool",
    "ToolRegistry",
    "Turn",
    "run_agent",
]
