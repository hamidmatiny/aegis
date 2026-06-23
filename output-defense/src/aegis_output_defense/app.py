from fastapi import FastAPI

from aegis_output_defense import __version__

app = FastAPI(title="AEGIS Output Defense", version=__version__)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "output-defense", "stage": "0"}
