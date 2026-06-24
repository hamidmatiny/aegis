"""CLI entrypoint for the AEGIS SDK reverse proxy."""

from __future__ import annotations

import uvicorn

from aegis_sdk.settings import settings


def main() -> None:
    uvicorn.run(
        "aegis_sdk.proxy.app:app",
        host=settings.sdk_proxy_host,
        port=settings.sdk_proxy_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
