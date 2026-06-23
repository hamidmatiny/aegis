"""FastAPI application for input defense detectors."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from aegis_input_defense import __version__
from aegis_input_defense.models import AnalyzeRequest, AnalyzeResponse, DetectorInfo, DetectorResult
from aegis_input_defense.service import InputDefenseService

app = FastAPI(
    title="AEGIS Input Defense",
    description="Input defense detector service with independent and fused analysis",
    version=__version__,
)

_service = InputDefenseService()


def get_service() -> InputDefenseService:
    return _service


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "input-defense", "stage": "2"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/detectors", response_model=list[DetectorInfo])
async def list_detectors() -> list[DetectorInfo]:
    return get_service().list_detectors()


@app.post("/detectors/{detector_id}/analyze", response_model=DetectorResult)
async def analyze_single(detector_id: str, body: AnalyzeRequest) -> DetectorResult:
    try:
        return await get_service().analyze_detector(
            detector_id,
            body.text,
            trusted_instruction=body.trusted_instruction,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_fused(body: AnalyzeRequest) -> AnalyzeResponse:
    verdict = await get_service().analyze_all(
        body.text,
        trusted_instruction=body.trusted_instruction,
        enabled_detectors=body.enabled_detectors,
    )
    return AnalyzeResponse(verdict=verdict)
