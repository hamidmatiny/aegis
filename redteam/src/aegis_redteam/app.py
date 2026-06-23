from fastapi import FastAPI

from aegis_redteam import __version__

app = FastAPI(title="AEGIS Red Team", version=__version__)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "redteam", "stage": "0"}
