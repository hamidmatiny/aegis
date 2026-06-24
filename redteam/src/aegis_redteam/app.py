"""FastAPI application for the red-team engine."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException

from aegis_redteam import __version__
from aegis_redteam.models import ProbeRequest, RunCampaignRequest
from aegis_redteam.probe.client import DefenseClient
from aegis_redteam.service import RedTeamService
from aegis_redteam.settings import settings

_service: RedTeamService | None = None
_client: DefenseClient | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _service, _client
    _client = DefenseClient(settings.input_defense_url, settings.output_defense_url)
    _service = RedTeamService(
        _client,
        threshold=settings.detection_threshold,
        database_url=settings.database_url,
        store_bypasses=settings.store_bypasses,
    )
    yield
    if _client:
        await _client.close()


app = FastAPI(
    title="AEGIS Red Team",
    description="Continuous adversarial testing against defense layers",
    version=__version__,
    lifespan=lifespan,
)


def get_service() -> RedTeamService:
    if _service is None:
        raise RuntimeError("service not initialized")
    return _service


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "redteam", "stage": "7"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/v1/strategies")
async def list_strategies() -> dict[str, list]:
    return {"strategies": get_service().list_strategies()}


@app.get("/v1/patterns")
async def list_patterns() -> dict[str, list]:
    return {"patterns": get_service().list_patterns()}


@app.post("/v1/probe")
async def probe(body: ProbeRequest) -> dict:
    try:
        return (await get_service().probe(body)).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/campaigns/run")
async def run_campaign(body: RunCampaignRequest) -> dict:
    try:
        return (await get_service().run_campaign(body)).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/campaigns")
async def list_campaigns() -> dict:
    return {"campaigns": [c.model_dump() for c in get_service().list_campaigns()]}


@app.get("/v1/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str) -> dict:
    try:
        return get_service().get_campaign(campaign_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
