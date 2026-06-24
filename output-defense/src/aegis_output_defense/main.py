"""CLI entrypoint."""

import uvicorn

from aegis_output_defense.settings import settings


def main() -> None:
    uvicorn.run(
        "aegis_output_defense.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
