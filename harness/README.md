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
  cheap/fast inference via `model-router`'s Ollama/vLLM support. Select
  which one a given run uses with `--provider` (see "Testing against a
  real model" below) — omit it and model-router falls back to its own
  configured default, which is `mock`.
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

Seven tools now (phase 1 shipped the first three; phase 2, the
operator-platform "tools/skills library" slice, added the other four),
each either reusing or newly registering a tool_name in
`policy-engine/policies/default.yaml`'s real `tool_catalog`, so the
governance paths they exercise are the platform's real ones. Between
them, all four risk tiers policy-engine defines are now exercised —
phase 1 alone left `HIGH` completely untested.

| Tool | Risk | Real policy path exercised |
|---|---|---|
| `search_docs` | LOW | Always allowed, still audited |
| `calculator` | LOW | Always allowed, still audited — pure arithmetic via a restricted `ast`-based evaluator, never Python `eval()` |
| `send_email` | MEDIUM | Allowed by default action, audited — writes to a local sandboxed outbox file, never a real mail server |
| `http_get` | MEDIUM | Allowed by default action, audited — GET only, refuses any host not on an explicit allowlist (default: `example.com` only) |
| `read_file` | MEDIUM | Allowed by default action, audited — confined to a local sandbox directory, refuses any path that would resolve outside it |
| `write_file` | HIGH | Allowed by default action (this pack has no HIGH-specific rule yet), audited — same sandbox containment as `read_file`, first starter tool to declare HIGH |
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

## Testing against a real model

Every run shown above under "Running it" only ever talks to
`model-router`'s `mock` provider, even with a real stack up — omitting
`--provider` (the default) makes model-router fall back to its own
configured `routing.default_provider`, which is `mock`
(`model-router/config/providers.yaml`). The `mock` provider just echoes
the last message back, so it can never produce this harness's expected
tool-call JSON on its own — useful for testing the loop's plumbing,
useless for seeing the agent actually decide anything. To see a real
model drive the loop, pick one of the two paths below.

**Path A — your own API key (works on any machine, no GPU/RAM needed).**
`model-router` already has provider integrations for OpenAI, Anthropic,
Gemini, and Grok (xAI) — you only need to supply a key, never touch
harness code:

```bash
# In the repo root .env (never paste a real key into chat/an issue/a PR) —
# see .env.example for the exact variable names model-router reads:
#   OPENAI_API_KEY=sk-...        (or ANTHROPIC_API_KEY / GOOGLE_API_KEY / XAI_API_KEY)
docker compose up -d model-router   # or the full stack

cd harness
pip install -e .
export AEGIS_MODEL_ROUTER_URL=http://localhost:8082
export AEGIS_AGENT_GATE_URL=http://localhost:8083
export AEGIS_INTERNAL_TOKEN=...      # from .env
export AEGIS_AGENT_GATE_API_KEYS=... # from .env, service key
aegis-harness --provider openai --model gpt-4o-mini \
  "search the docs for how onboarding works"
```

Swap `--provider openai --model gpt-4o-mini` for `--provider anthropic
--model claude-3-5-haiku-20241022`, `--provider gemini --model
gemini-1.5-flash`, or `--provider grok --model grok-4.3` — whichever key
you actually have set. Costs are whatever that provider bills for a
handful of short chat completions (typically well under a cent per run
with these small/fast default models).

**Path B — a local model via Ollama/vLLM (free, needs real RAM/VRAM).**
`model-router` already supports both as providers; nothing in this
harness needs to change:

- **Ollama**: install it and pull a small model on the machine
  `model-router` runs on (or reachable from it): `ollama pull llama3`,
  then make sure `ollama serve` is running. `model-router`'s `ollama`
  provider is enabled by default and points at
  `http://host.docker.internal:11434/v1`, which reaches an Ollama
  instance running on the Docker host — override with `OLLAMA_BASE_URL`
  in `.env` if yours runs elsewhere. Then:
  `aegis-harness --provider ollama --model llama3 "..."`. This needs
  real memory for the model itself (llama3-8B wants roughly 5-8GB free,
  depending on quantization) — small enough for most laptops, generally
  too much for a small cloud VM like the ones this project's own Oracle
  demo box uses, which is why this is documented as something *you* run
  locally, not something the demo stack ships running.
- **vLLM**: disabled by default in `model-router/config/providers.yaml`
  (`vllm.enabled: false`) since it expects a GPU-backed vLLM server
  already running at `base_url` (`http://localhost:8000/v1` by default).
  Enable it by setting `enabled: true` there (or pointing
  `AEGIS_MODEL_ROUTER_CONFIG` at your own copy of the file), start your
  vLLM server separately, then run with `--provider vllm --model
  <your-served-model-name>`.

**A note on `--provider` and fallback.** If you request a provider that
isn't actually registered (disabled, or a typo), `model-router` doesn't
error — it silently falls through its configured `fallback_chain`
(`openai` → `anthropic` → `grok` → `ollama` → `mock`, in the default
config), which can quietly land you on a *different* real provider, or
on `mock`, rather than an obvious failure. If a run's output looks like
a plain echo of your message, that's the tell that it silently fell all
the way back to `mock` — check `model-router`'s logs or `GET
/v1/providers` to see what's actually enabled and reachable before
assuming a `--provider` flag "didn't work."

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

`tests/test_clients.py` also verifies the `provider` field's exact
on-the-wire behavior — present and correct when `--provider` is set,
genuinely absent (not `provider: ""`) when it isn't, which is what makes
model-router's own fallback-to-`mock` default the one you get unless you
opt out of it. `tests/test_loop.py` verifies `run_agent()` forwards
whatever `provider` it's given to `model_client.complete()` unchanged on
every turn.

What still isn't verified here, and can't be from this sandbox: an
actual end-to-end run against a live `docker-compose` stack talking to a
real OpenAI/Anthropic/Gemini/Grok account or a real local Ollama/vLLM
model. That requires either billing credentials or GPU/RAM this
environment doesn't have — which is exactly why "Testing against a real
model" above exists as a documented, generalized path for anyone (not
just whoever built this) to close that last gap themselves, rather than
this being worked around by teaching the harness to game the mock
provider's trivial echo behavior, which would prove nothing real.
