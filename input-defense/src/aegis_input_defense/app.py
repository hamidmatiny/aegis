"""FastAPI application for input defense detectors."""

from __future__ import annotations

from fastapi import FastAPI

from aegis_input_defense import __version__

app = FastAPI(
    title="AEGIS Input Defense",
    description="Input defense detector service (heuristic, perplexity, classifier, fusion)",
    version=__version__,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "input-defense", "stage": "0"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
