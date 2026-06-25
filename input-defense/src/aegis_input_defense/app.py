"""FastAPI application for input defense detectors."""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException

from aegis_input_defense import __version__
from aegis_input_defense.audit_client import AuditClient
from aegis_input_defense.models import AnalyzeRequest, AnalyzeResponse, DetectorInfo, DetectorResult
from aegis_input_defense.service import InputDefenseService
from aegis_input_defense.ml.loader import warmup_models
from aegis_input_defense.settings import settings

app = FastAPI(
    title="AEGIS Input Defense",
    description="Input defense detector service with independent and fused analysis",
    version=__version__,
)

_service = InputDefenseService()
_audit = AuditClient(settings.audit_url) if settings.emit_audit else AuditClient("")


def get_service() -> InputDefenseService:
    return _service


async def _emit_input_audit(body: AnalyzeRequest, verdict: AnalyzeResponse) -> None:
    if body.trace and body.trace.request_id and not verdict.verdict.request_id:
        verdict.verdict.request_id = body.trace.request_id
    await _audit.emit_input_verdict(
        tenant_id=body.tenant_id,
        trace=body.trace,
        verdict=verdict.verdict,
        policy_pack_id=body.policy_pack_id or "",
        policy_pack_version=body.policy_pack_version or "",
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "input-defense", "stage": "2"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    try:
        warmup_models(
            prompt_guard=settings.classifier_backend == "prompt-guard",
            perplexity=settings.perplexity_backend == "lm",
            prompt_guard_model_id=settings.prompt_guard_model_id,
            perplexity_model_id=settings.perplexity_model_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"model warmup failed: {exc}") from exc
    return {
        "status": "ready",
        "classifier_backend": settings.classifier_backend,
        "perplexity_backend": settings.perplexity_backend,
    }


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
            request_id=body.trace.request_id if body.trace else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_fused(body: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    verdict = await get_service().analyze_all(
        body.text,
        trusted_instruction=body.trusted_instruction,
        enabled_detectors=body.enabled_detectors,
        request_id=body.trace.request_id if body.trace else None,
    )
    response = AnalyzeResponse(verdict=verdict)
    if _audit.enabled:
        background_tasks.add_task(_emit_input_audit, body, response)
    return response
