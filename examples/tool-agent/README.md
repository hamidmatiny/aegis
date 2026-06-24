# Tool-using agent

Simulates an LLM choosing a tool call and routes it through **agent-gate** (policy + sanitization + human approval).

## Prerequisites (once per machine)

From the **repository root**:

```bash
cp .env.example .env
docker compose up -d agent-gate policy-engine
curl -sf http://localhost:8083/health
curl -sf http://localhost:8081/health
```

Optional (for embedded SDK mode — calls services directly):

```bash
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

Use raw HTTP to agent-gate instead of embedded SDK:

```bash
python tool_agent.py --scenario safe-search --http
```

### After `irreversible-delete`: approve in the dashboard or curl

The script prints an `approval_id`. Example:

```bash
curl -X POST "http://localhost:8083/v1/approvals/appr-XXXXXXXX/decide" \
  -H 'Content-Type: application/json' \
  -d '{"approved": true, "reviewer_id": "demo-operator", "comment": "Emergency maintenance"}'
```

Or open the dashboard at http://localhost:3000 → **Approvals**.

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

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Connection refused :8083 | `docker compose up -d agent-gate policy-engine` |
| `policy pack not found` | Ensure policy-engine is healthy and policies volume is mounted |
| Approval expired | Re-run `--scenario irreversible-delete` to mint a new `approval_id` |
