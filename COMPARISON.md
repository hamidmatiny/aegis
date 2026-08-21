# AEGIS vs. other open-source LLM/agent guardrails

Written for engineers evaluating options, not marketing. Corrections
welcome via an issue or PR if something here goes stale or is wrong —
these are point-in-time comparisons of fast-moving projects.

| | AEGIS | NVIDIA NeMo Guardrails | Guardrails AI | LLM Guard |
|---|---|---|---|---|
| GitHub stars (approx., 2026) | new | ~6.5k | ~3.5k | — |
| Input/output text filtering (prompt injection, PII, toxicity) | Yes | Yes | Yes | Yes |
| Agent tool/plugin permissioning (blocks unauthorized tool calls) | **Yes** (`agent-gate`: taint tracking + policy-gated tool execution + human approval for irreversible actions) | No | No | No |
| Tamper-evident audit trail | **Yes** (Ed25519-signed receipts, `audit` service) | No | No | No |
| Published adaptive red-team results (not just round-1 catch rate) | **Yes** — [RESULTS.md](./RESULTS.md), including an unflattering one | Not found | Not found | Not found |
| Continuous adversarial monitoring (ongoing, not one-time) | **Yes** (`redteam` service, the same one that produced the published numbers) | No | No | No |
| Reverse-proxy drop-in (`OPENAI_BASE_URL` swap, zero app code changes) | Yes | Partial (library, not a proxy) | Partial (library, not a proxy) | Partial (library, not a proxy) |
| License | Apache 2.0 | Apache 2.0 | Apache 2.0 | MIT |

## Why this list, not a bigger one

These three are the most-referenced open-source options in the "LLM
guardrails" space as of 2026. If there's a project doing agent/tool-use
permissioning or publishing adaptive (not just static) red-team numbers that
should be on this list, open an issue.

## The two differences that actually matter

**Scope.** NeMo Guardrails, Guardrails AI, and LLM Guard all operate on the
text going into and out of a model call. None of them govern what an agent
is allowed to *do* — call a tool, hit an API, touch a database. Tool/plugin
misuse via prompt injection is a widely-cited, largely-unaddressed risk in
current agent security writing. `agent-gate` is what AEGIS has that the
others don't: taint tracking through a request and a policy-gated
permission check before a tool call executes, with human approval required
for irreversible actions.

**Honesty about detection limits.** Every guardrail vendor, AEGIS included,
can report a round-1 catch rate against a fixed test set and make it look
good — that number is close to meaningless against a real attacker who
adapts. [RESULTS.md](./RESULTS.md) reports adaptive red-teaming that breeds
new attacks from prior bypasses. **Methodology:** publish **R1 BR** (static
catch on the full corpus) and **Adapt BR** (bypass rate on rounds 2+,
conditional on prior-round survivors) **separately** — do not blend them into
one “overall bypass rate” headline. The archival H3 frozen-corpus run on
`main` still shows round tables including a historical overall figure; a
multi-corpus RESULTS rewrite (held-out / reserved blind grades) is tracked
separately pending review. The product posture is continuous monitoring via
`redteam/`, not a one-time install that claims the problem is solved. None of
the other three projects publish adaptive numbers at all, which doesn't mean
they'd do worse — it means there's no way to know.

**Defense-in-depth vs text-only peers.** Most open-source guardrails stop at
input/output filtering. AEGIS also ships **agent-gate** + a tool risk catalog
(and a governed **harness** that will not execute a tool without an allow
decision). That matters for tool-misuse classes — and it is honest to say
content classification remains the load-bearing layer for attacks that never
become tool calls. See [ARCHITECTURE.md](./ARCHITECTURE.md).

## When one of the others might be a better fit

- **Just need conversational guardrails for a chatbot, no agents/tools involved:** NeMo Guardrails' Colang DSL for multi-turn dialog flow control is more mature for that narrow case.
- **Already deep in the Guardrails AI ecosystem** (validators, hub): switching cost may not be worth it for text-only filtering needs.
- **Need the absolute smallest dependency footprint:** LLM Guard is lighter-weight if you only need a filtering library, not a proxy/platform.
