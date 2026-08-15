"""Real httpx round-trip tests for ModelRouterClient and AgentGateClient
against local mock HTTP servers standing in for model-router and
agent-gate -- not stubs of the client itself, real network calls to a
real (if fake) server on localhost, so request shape, headers, and
response parsing are all genuinely exercised. Same pattern this project
has used since Stage E.1/E.2 for verifying HTTP client code without a
live Docker stack.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aegis_harness.clients import AgentGateClient, ModelRouterClient


class _RecordingHandler(BaseHTTPRequestHandler):
    """Records every request it receives (method, path, headers, parsed
    JSON body) onto the class-level `requests` list, and looks up a
    scripted (status, body) response from `responses` keyed by
    "METHOD path". Approvals polling needs multiple different responses
    for the *same* path across calls -- `poll_responses` is consumed in
    order, falling back to `responses` once exhausted."""

    requests: list[dict] = []
    responses: dict[str, tuple[int, dict]] = {}
    poll_responses: list[dict] = []

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""
        body = json.loads(raw_body) if raw_body else None
        self.__class__.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": body,
            }
        )

        is_approval_poll = self.command == "GET" and self.path.startswith("/v1/approvals/")
        if is_approval_poll and self.__class__.poll_responses:
            status_code, resp_body = 200, self.__class__.poll_responses.pop(0)
        else:
            key = f"{self.command} {self.path}"
            if key not in self.__class__.responses:
                # Fall back to a prefix match for /v1/approvals/<id>
                matched = [
                    k for k in self.__class__.responses
                    if self.path.startswith(k.split(" ", 1)[1])
                ]
                if matched:
                    key = f"{self.command} {matched[0].split(' ', 1)[1]}"
            status_code, resp_body = self.__class__.responses.get(
                key, (404, {"error": "not found"})
            )

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp_body).encode())

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def log_message(self, format, *args):  # noqa: A002 -- silence test output
        pass


@pytest.fixture
def mock_server():
    _RecordingHandler.requests = []
    _RecordingHandler.responses = {}
    _RecordingHandler.poll_responses = []
    server = HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}", _RecordingHandler
    server.shutdown()
    thread.join(timeout=5)


@pytest.mark.asyncio
async def test_model_router_client_sends_internal_token_header(mock_server):
    base_url, handler = mock_server
    handler.responses["POST /v1/chat/completions"] = (
        200,
        {"content": "hello back", "provider": "mock", "model": "mock-model"},
    )
    client = ModelRouterClient(base_url=base_url, internal_token="secret-token", trust_env=False)

    result = await client.complete(model="mock-model", messages=[{"role": "user", "content": "hi"}])

    assert result == "hello back"
    assert len(handler.requests) == 1
    req = handler.requests[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer secret-token"
    assert req["body"] == {"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]}


@pytest.mark.asyncio
async def test_model_router_client_omits_header_when_no_token(mock_server):
    base_url, handler = mock_server
    handler.responses["POST /v1/chat/completions"] = (200, {"content": "x"})
    client = ModelRouterClient(base_url=base_url, internal_token="", trust_env=False)

    await client.complete(model="mock-model", messages=[])

    assert "Authorization" not in handler.requests[0]["headers"]


@pytest.mark.asyncio
async def test_model_router_client_raises_on_missing_content(mock_server):
    base_url, handler = mock_server
    handler.responses["POST /v1/chat/completions"] = (200, {"provider": "mock"})
    client = ModelRouterClient(base_url=base_url, trust_env=False)

    with pytest.raises(ValueError, match="missing string 'content'"):
        await client.complete(model="mock-model", messages=[])


@pytest.mark.asyncio
async def test_agent_gate_client_evaluate_request_shape_and_allowed(mock_server):
    base_url, handler = mock_server
    handler.responses["POST /v1/evaluate"] = (
        200,
        {"decision": {"status": "APPROVED"}, "sanitized_tool_call": {}},
    )
    client = AgentGateClient(
        base_url=base_url, service_api_key="svc-key", tenant_id="acme", trust_env=False
    )

    decision = await client.evaluate(
        tool_name="search_docs",
        arguments={"query": "onboarding"},
        agent_id="agent-1",
        risk_level="LOW",
    )

    assert decision.allowed is True
    assert decision.status == "APPROVED"
    req = handler.requests[0]
    assert req["headers"]["Authorization"] == "Bearer svc-key"
    assert req["body"]["tenant_id"] == "acme"
    assert req["body"]["mode"] == "enforce"
    tool_call = req["body"]["tool_call"]
    assert tool_call["tool_name"] == "search_docs"
    assert tool_call["agent_id"] == "agent-1"
    assert tool_call["risk_level"] == "LOW"
    assert tool_call["arguments"] == [{"name": "query", "value": "onboarding"}]


@pytest.mark.asyncio
async def test_agent_gate_client_evaluate_denied(mock_server):
    base_url, handler = mock_server
    handler.responses["POST /v1/evaluate"] = (
        200,
        {"decision": {"status": "DENIED", "denial_reason": "blocked by policy"}},
    )
    client = AgentGateClient(base_url=base_url, service_api_key="svc-key", trust_env=False)

    decision = await client.evaluate(tool_name="x", arguments={}, agent_id="a")

    assert decision.allowed is False
    assert decision.denial_reason == "blocked by policy"


@pytest.mark.asyncio
async def test_agent_gate_client_evaluate_omits_risk_level_when_not_given(mock_server):
    base_url, handler = mock_server
    handler.responses["POST /v1/evaluate"] = (200, {"decision": {"status": "APPROVED"}})
    client = AgentGateClient(base_url=base_url, service_api_key="svc-key", trust_env=False)

    await client.evaluate(tool_name="x", arguments={}, agent_id="a")

    assert "risk_level" not in handler.requests[0]["body"]["tool_call"]


@pytest.mark.asyncio
async def test_wait_for_approval_polls_until_decided(mock_server):
    base_url, handler = mock_server
    handler.poll_responses = [
        {"status": "AWAITING_HUMAN_APPROVAL", "approval_id": "appr-1"},
        {"status": "AWAITING_HUMAN_APPROVAL", "approval_id": "appr-1"},
        {"status": "APPROVED", "approval_id": "appr-1", "review_comment": "looks fine"},
    ]
    client = AgentGateClient(base_url=base_url, service_api_key="svc-key", trust_env=False)

    decision = await client.wait_for_approval(
        "appr-1", timeout_seconds=5.0, poll_interval_seconds=0.01
    )

    assert decision.status == "APPROVED"
    assert decision.denial_reason == "looks fine"
    # Polled exactly 3 times (2 pending + 1 resolved), not more, not fewer
    get_requests = [r for r in handler.requests if r["method"] == "GET"]
    assert len(get_requests) == 3
    assert all(r["path"] == "/v1/approvals/appr-1" for r in get_requests)


@pytest.mark.asyncio
async def test_wait_for_approval_times_out_if_never_decided(mock_server):
    base_url, handler = mock_server
    handler.poll_responses = [
        {"status": "AWAITING_HUMAN_APPROVAL", "approval_id": "appr-2"}
    ] * 50  # far more than the short timeout below could ever consume

    client = AgentGateClient(base_url=base_url, service_api_key="svc-key", trust_env=False)

    decision = await client.wait_for_approval(
        "appr-2", timeout_seconds=0.05, poll_interval_seconds=0.01
    )

    assert decision.status == "TIMED_OUT"
