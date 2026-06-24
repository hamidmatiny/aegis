"""CLI entrypoint."""

import uvicorn

from aegis_redteam.settings import settings


def main() -> None:
    uvicorn.run(
        "aegis_redteam.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
