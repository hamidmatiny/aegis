"""CLI entrypoint and FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from aegis_corp_orchestrator import __version__
from aegis_corp_orchestrator.config import settings
from aegis_corp_orchestrator.db.migrate import apply_migrations
from aegis_corp_orchestrator.routers.agents import router as agents_router
from aegis_corp_orchestrator.routers.bev import router as bev_router
from aegis_corp_orchestrator.runner.scheduler import scheduler_loop
from aegis_corp_orchestrator.seed import seed_agents

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_stop = asyncio.Event()
_sched_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _sched_task
    apply_migrations()
    seed_agents()
    _stop.clear()
    _sched_task = asyncio.create_task(scheduler_loop(_stop))
    yield
    _stop.set()
    if _sched_task is not None:
        try:
            await asyncio.wait_for(_sched_task, timeout=5.0)
        except (TimeoutError, asyncio.CancelledError):
            _sched_task.cancel()


app = FastAPI(title="AEGIS Corp Orchestrator", version=__version__, lifespan=lifespan)
app.include_router(agents_router)
app.include_router(bev_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "corp-orchestrator", "version": __version__}


def main() -> None:
    uvicorn.run(
        "aegis_corp_orchestrator.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
