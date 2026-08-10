# Tool-using agent

Simulates an LLM choosing a tool call and routes it through **agent-gate** (policy + sanitization + human approval).

## Prerequisites (once per machine)

From the **repository root**:

```bash
cp .env.example .env
./scripts/generate-credentials.sh   # fills in AEGIS_AGENT_GATE_API_KEYS / _REVIEWER_KEYS, among others
docker compose up -d agent-gate policy-engine
curl -sf http://localhost:8083/health
curl -sf http://localhost:8081/health
```

agent-gate requires two separate API keys (see `agent-gate/internal/auth`):
a **service key** (`AEGIS_AGENT_GATE_API_KEYS`) for submitting tool calls, and
a **reviewer key** (`AEGIS_AGENT_GATE_REVIEWER_KEYS`) for deciding an
approval — deliberately different, so this script's own service key can
never approve its own irreversible action. Export both from `.env`:

```bash
export $(grep -E '^AEGIS_AGENT_GATE_(API_KEYS|REVIEWER_KEYS)=' .env | xargs)
export AEGIS_AGENT_GATE_URL=http://localhost:8083
export AEGIS_POLICY_ENGINE_URL=http://localhost:8081
```

## Virtual environment setup

From **this directory** (`examples/tool-agent/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../../sdk/python
pip install httpx
```

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ..\..\sdk\python
pip install httpx
```

## Run commands

Stay in `examples/tool-agent/` with the venv activated.

**1. Safe read-only tool (approved):**

```bash
python tool_agent.py --scenario safe-search
```

**2. Irreversible action (human approval required):**

```bash
python tool_agent.py --scenario irreversible-delete
```

**3. Tainted credentials in tool arguments (denied):**

```bash
python tool_agent.py --scenario credential-leak
```

**4. Caller understates risk_level for a registered tool (still escalated):**

```bash
python tool_agent.py --scenario risk-spoof-blocked
```

Use raw HTTP to agent-gate instead of embedded SDK:

```bash
python tool_agent.py --scenario safe-search --http
```

### After `irreversible-delete`: approve in the dashboard or curl

The script prints an `approval_id`. Approving requires the **reviewer key**,
not the service key used to submit the call:

```bash
curl -X POST "http://localhost:8083/v1/approvals/appr-XXXXXXXX/decide" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AEGIS_AGENT_GATE_REVIEWER_KEYS" \
  -d '{"approved": true, "reviewer_id": "demo-operator", "comment": "Emergency maintenance"}'
```

Or open the dashboard at http://localhost:3000 → **Approvals** (the dashboard
holds the reviewer key server-side, behind its own login).

## What attacks does this demonstrate?

Agent-gate enforces permissions **in code**, not via prompt instructions. Three policy outcomes:

### Scenario A — `safe-search`: allowed tool

| Field | Value |
|-------|--------|
| **Tool** | `search_docs` |
| **Risk** | `LOW` |
| **Expected** | `RESULT: APPROVED` |

**Example output:**

```
=== Scenario: Low-risk tool — allowed ===

LLM-selected tool call:
{
  "tool_name": "search_docs",
  "risk_level": "LOW",
  "arguments": [{"name": "query", "value": "deployment runbook", "taint_level": "TRUSTED"}]
}

RESULT: APPROVED
```

---

### Scenario B — `irreversible-delete`: **human-in-the-loop for destructive actions**

**Attack / risk:** Compromised or misaligned agent attempts **irreversible** damage (`delete_database` on production).

| Field | Value |
|-------|--------|
| **Tool** | `delete_database` |
| **Risk** | `IRREVERSIBLE` |
| **Policy rule** | `require-approval-irreversible` → `escalate_to_judge` |
| **Expected** | `RESULT: AWAITING_HUMAN_APPROVAL` + `approval_id` |

**Example output:**

```
=== Scenario: Irreversible tool — human approval required ===

LLM-selected tool call:
{
  "tool_name": "delete_database",
  "risk_level": "IRREVERSIBLE",
  "arguments": [{"name": "db_id", "value": "prod-analytics", "taint_level": "TRUSTED"}]
}

RESULT: AWAITING_HUMAN_APPROVAL
  approval_id: appr-1740000000123456789
  Next: approve via dashboard or:
    curl -X POST localhost:8083/v1/approvals/appr-.../decide ...
```

The tool **does not execute** until a human approves via `/v1/approvals/{id}/decide`.

---

### Scenario C — `credential-leak`: **taint + secret exfiltration blocked**

**Attack:** Agent tries to send **tainted** content containing secrets via `send_email`.

| Field | Value |
|-------|--------|
| **Argument** | `body` with `password: hunter2`, `taint_level: TAINTED`, `contains_credentials: true` |
| **Policy rule** | `block-tainted-credentials` |
| **Expected** | `RESULT: DENIED` |

**Example output:**

```
=== Scenario: Tainted credentials in tool args — denied ===

LLM-selected tool call:
{
  "tool_name": "send_email",
  "risk_level": "MEDIUM",
  "arguments": [
    {
      "name": "body",
      "value": "password: hunter2 api_key=sk-secret-leak-123",
      "taint_level": "TAINTED",
      "contains_credentials": true
    }
  ]
}

RESULT: DENIED
  reason: blocked by policy
```

If credentials appear in arguments, agent-gate may also return a **sanitized** tool call with `[REDACTED-*]` placeholders in the HTTP response (see `--http` mode JSON).

---

### Scenario D — `risk-spoof-blocked`: **a caller can't talk its way out of approval**

**Attack / risk:** `tool_call.risk_level` is set by whatever assembles the call — in a real
integration, that can ultimately be influenced by the LLM's own output. Before this fix,
declaring `risk_level: "LOW"` on a `delete_database` call skipped approval entirely and the
call was `APPROVED` outright. That's the gap our own agent-gate red-teaming found.

| Field | Value |
|-------|--------|
| **Tool** | `delete_database` (registered in `policy-engine/policies/default.yaml` `tool_catalog` as `IRREVERSIBLE`) |
| **Declared risk_level** | `LOW` |
| **Effective risk_level** | `IRREVERSIBLE` (catalog wins — see `policy-engine/internal/engine/risk.go`) |
| **Expected** | `RESULT: AWAITING_HUMAN_APPROVAL`, with `risk_level_overridden: true` in the response |

The response's `denial_reason` spells out exactly what happened: the declared risk was
overridden by the registered catalog entry. Register any tool whose misuse would be
destructive, irreversible, or high-blast-radius in `tool_catalog` — an unregistered tool
still falls back to trusting the caller's declared `risk_level`, which is a documented trust
boundary, not a bug: agent-gate can't know about tools it's never been told exist.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Connection refused :8083 | `docker compose up -d agent-gate policy-engine` |
| `policy pack not found` | Ensure policy-engine is healthy and policies volume is mounted |
| Approval expired | Re-run `--scenario irreversible-delete` to mint a new `approval_id` |
