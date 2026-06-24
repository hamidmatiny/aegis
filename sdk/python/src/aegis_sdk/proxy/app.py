"""FastAPI reverse-proxy exposing OpenAI-compatible endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from aegis_sdk import __version__
from aegis_sdk.errors import (
    AegisApprovalRequiredError,
    AegisPolicyBlockedError,
    AegisProviderError,
)
from aegis_sdk.pipeline import DefensePipeline
from aegis_sdk.settings import settings

app = FastAPI(
    title="AEGIS SDK Proxy",
    description="OpenAI-compatible reverse proxy with defense-in-depth",
    version=__version__,
)

_pipeline = DefensePipeline(
    input_defense_url=settings.input_defense_url,
    output_defense_url=settings.output_defense_url,
    policy_engine_url=settings.policy_engine_url,
    model_router_url=settings.model_router_url,
    agent_gate_url=settings.agent_gate_url,
    tenant_id=settings.default_tenant_id,
)


class ChatCompletionRequest(BaseModel):
    model: str = Field(default_factory=lambda: settings.default_model)
    messages: list[dict[str, Any]]
    provider: str | None = None
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class ToolEvaluateRequest(BaseModel):
    tool_call: dict[str, Any]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aegis-sdk-proxy", "stage": "10"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest) -> Response:
    try:
        result = await _pipeline.chat_completions(
            model=body.model,
            messages=body.messages,
            provider=body.provider,
            stream=body.stream,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        return JSONResponse(content=result)
    except AegisPolicyBlockedError as exc:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "type": "aegis_policy_blocked",
                    "message": str(exc),
                    "layer": exc.layer,
                    "policy_action": exc.policy_action,
                    "action": exc.action,
                    "fused_score": exc.fused_score,
                }
            },
        )
    except AegisProviderError as exc:
        status = exc.status_code or 502
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "type": exc.error_type or "aegis_provider_error",
                    "message": str(exc),
                    "provider": exc.provider,
                    "model": exc.model,
                },
                "aegis": exc.details,
            },
        )


@app.post("/v1/tools/evaluate")
async def evaluate_tool(body: ToolEvaluateRequest) -> Response:
    try:
        result = await _pipeline.evaluate_tool(tool_call=body.tool_call)
        return JSONResponse(content=result)
    except AegisApprovalRequiredError as exc:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "type": "aegis_approval_required",
                    "message": str(exc),
                    "approval_id": exc.approval_id,
                    "tool_name": exc.tool_name,
                }
            },
        )
    except AegisPolicyBlockedError as exc:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "type": "aegis_policy_blocked",
                    "message": str(exc),
                    "layer": exc.layer,
                }
            },
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
