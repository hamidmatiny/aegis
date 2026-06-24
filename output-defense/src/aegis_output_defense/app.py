"""FastAPI application for output defense detectors."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from aegis_output_defense import __version__
from aegis_output_defense.models import AnalyzeRequest, AnalyzeResponse, DetectorInfo, DetectorResult
from aegis_output_defense.service import OutputDefenseService

app = FastAPI(
    title="AEGIS Output Defense",
    description="Output defense detector service with independent and fused analysis",
    version=__version__,
)

_service = OutputDefenseService()


def get_service() -> OutputDefenseService:
    return _service


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "output-defense", "stage": "5"}


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
            body.content,
            original_prompt=body.original_prompt,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_fused(body: AnalyzeRequest) -> AnalyzeResponse:
    verdict = await get_service().analyze_all(
        body.content,
        original_prompt=body.original_prompt,
        enabled_detectors=body.enabled_detectors,
    )
    return AnalyzeResponse(verdict=verdict)
