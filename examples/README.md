# AEGIS example applications (Stage 11)

Three self-contained demos you can hand to someone with **no prior context**. Each has its own README with exact venv commands, run commands, and attack walkthroughs with example input/output.

## Start the platform once

From the **repository root**:

```bash
cp .env.example .env
docker compose up -d gateway input-defense output-defense policy-engine model-router agent-gate audit
```

Wait until health checks pass:

```bash
curl -sf http://localhost:8080/health
curl -sf http://localhost:8083/health
```

## Examples

| App | Directory | Demonstrates |
|-----|-----------|--------------|
| **Defended chatbot** | [chatbot/](chatbot/) | Direct prompt injection blocked before LLM |
| **RAG + taint** | [rag-taint/](rag-taint/) | Indirect injection in retrieved docs; tainted tool exfil denied |
| **Tool-using agent** | [tool-agent/](tool-agent/) | Irreversible tools need approval; tainted credentials blocked |

## Quick copy-paste

**Chatbot:**

```bash
cd examples/chatbot
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../../sdk/python
python chatbot.py --demo injection
```

**RAG:**

```bash
cd examples/rag-taint
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../../sdk/python
python rag_taint.py --scenario injection-rag
```

**Tool agent:**

```bash
cd examples/tool-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../../sdk/python
python tool_agent.py --scenario irreversible-delete
```

## Automated smoke test

From repo root (stack must be running):

```bash
./scripts/e2e-examples.sh
```

## Shared dependency

All examples install the local Python SDK:

```bash
pip install -e ../../sdk/python
```

Run these commands from inside each example directory. See each app's README for full prerequisites and expected output.
