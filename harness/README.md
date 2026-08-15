# AEGIS harness

Operator-platform phase 1. A minimal, real, **governed** multi-step agent
loop — the first concrete piece of the "model layer + harness +
tools/skills library + runtime holding it together" vision, grown from
inside AEGIS itself rather than a new repo.

This is not a general-purpose agent framework. LangChain, CrewAI, AutoGen,
and OpenAI's own Agents SDK already do that well, and re-building it here
wouldn't be differentiated. What AEGIS actually has that's rare is a
tested, self-approval-proof governance layer (`agent-gate` +
`policy-engine`) — until now, that layer was purely advisory: it only
mattered if whatever called it chose to. This harness makes it
**load-bearing**: there is exactly one line of code in this whole package
that can call a tool's real implementation
(`loop.py`'s `_execute_after_gate`), and it refuses to run without an
`ALLOWED` decision from agent-gate. Removing or routing around the gate
call in `run_agent` would take actively deleting code, not just forgetting
a step.

## What it does

```
model-router (next action) → agent-gate (governance) → tool.execute() → repeat
```

`run_agent()` runs a bounded loop: ask `model-router` for the next step,
parse the response as either a tool call or a final answer, and if it's a
tool call, submit it to `agent-gate` *before* running it. An
`IRREVERSIBLE`-risk tool call gets escalated to human approval and the
loop genuinely pauses — polling `agent-gate` until a reviewer decides it
or a timeout elapses — not a simulated pause.

## Why model-router needs a prompted convention, not native tool-calling

`model-router`'s API (`ChatRequest`/`ChatResponse` in
`model-router/internal/models/types.go`) is plain text in, text out — no
`tools`/`tool_calls` fields, and none of its providers (including the
`mock` one) implement OpenAI-style native function-calling. Adding that
to model-router itself is a real change to a shared core service, out of
scope here and not done silently — see `protocol.py`'s module docstring.
Until then, `protocol.py` uses the older, still-effective pattern: the
system prompt describes available tools and asks the model to respond
with a specific JSON shape to call one, and `parse_model_response` is
tolerant of a model wrapping that JSON in prose or a code fence.

## Extending this later without a rewrite

This was built with one explicit requirement: adding capability later
shouldn't mean restructuring what's already here.

- **New tools**: implement `Tool` (`tool.py`) and register an instance
  with a `ToolRegistry`. The loop never changes.
- **New model providers**: nothing to do here — add the provider to
  `model-router`'s own config, and it's available to every harness run
  through the existing `ModelRouterClient`, including self-hosted
  cheap/fast inference via `model-router`'s Ollama/vLLM support.
- **New invocation surfaces**: `run_agent()` is a plain importable async
  function, entirely separate from `cli.py`'s argument parsing. Wrapping
  it in an HTTP service later (`POST /v1/harness/run`, say) means writing
  a handler that calls the same function and serializes the same
  `AgentRunResult` — additive, not a restructure.
- **Multi-agent / planning variants**: `run_agent()` intentionally keeps
  the tool-execution and governance plumbing (the actually hard, tested
  part) separate from the specific single-loop control flow, so a future
  harness variant can reuse `Tool`, `ToolRegistry`, `GateClient`, and
  `ModelClient` without re-implementing any of it.

## Starter tools

Three tools, deliberately reusing tool_names already registered in
`policy-engine/policies/default.yaml`'s real `tool_catalog`, so the
governance paths they exercise are the platform's real ones:

| Tool | Risk | Real policy path exercised |
|---|---|---|
| `search_docs` | LOW | Always allowed, still audited |
| `send_email` | MEDIUM | Allowed by default action, audited — writes to a local sandboxed outbox file, never a real mail server |
| `delete_database` | IRREVERSIBLE | Escalated to human approval via `require-approval-irreversible` — operates on a sandboxed placeholder file, never real Postgres, so triggering the real approval pause in a demo is harmless |

## Running it

Against a running AEGIS stack (`docker compose up -d`):

```bash
cd harness
pip install -e .
export AEGIS_MODEL_ROUTER_URL=http://localhost:8082
export AEGIS_AGENT_GATE_URL=http://localhost:8083
export AEGIS_INTERNAL_TOKEN=...      # from .env
export AEGIS_AGENT_GATE_API_KEYS=... # from .env, service key (first of the comma list)
aegis-harness "search the docs for how onboarding works"
```

To see the human-approval pause for real, ask it to do something that
maps to `delete_database` and, in another terminal, decide the approval
with the **reviewer** key (never the service key — see
`agent-gate/README.md` on why those are deliberately separate):

```bash
curl -X POST localhost:8083/v1/approvals/<id>/decide \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AEGIS_AGENT_GATE_REVIEWER_KEYS" \
  -d '{"approved": true, "reviewer_id": "demo", "comment": "ok"}'
```

## Honest scope of what's verified here

The loop's control flow — turn budget, unknown-tool handling, the gate
decision branches (allow / deny / escalate-and-wait / timeout), and the
one-and-only path to `tool.execute()` — is exercised by real `pytest`
runs against scripted stub clients (`tests/test_loop.py`), not just
reasoned about. The real HTTP clients (`ModelRouterClient`,
`AgentGateClient`) are exercised by real `httpx` round trips against
local mock HTTP servers standing in for model-router and agent-gate
(`tests/test_clients.py`) — request shapes, headers (including the
`AEGIS_INTERNAL_TOKEN` model-router now enforces), and response parsing
are genuinely tested, not assumed correct by inspection.

What isn't verified here: an actual end-to-end run against a live
`docker-compose` stack. `model-router`'s `mock` provider just echoes the
last message back (`model-router/internal/provider/mock.go`) — it has no
model-like ability to produce this harness's expected tool-call JSON on
its own, so a genuinely meaningful live run needs either a real provider
API key or an Ollama/vLLM model actually capable of following the
tool-call instruction in the system prompt. This is disclosed here
rather than worked around by teaching the harness to game the mock
provider's trivial echo behavior, which would prove nothing real.
