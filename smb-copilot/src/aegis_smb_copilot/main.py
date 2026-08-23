"""CLI entrypoint and bare FastAPI application."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from aegis_smb_copilot import __version__
from aegis_smb_copilot.config import settings
from aegis_smb_copilot.routers import billing, onboarding, qa

app = FastAPI(title="AEGIS SMB Copilot", version=__version__)
app.include_router(onboarding.router)
app.include_router(qa.router)
app.include_router(billing.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "smb-copilot", "version": __version__}


def main() -> None:
    uvicorn.run(
        "aegis_smb_copilot.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
