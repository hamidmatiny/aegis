"""Service configuration."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_INPUT_DEFENSE_")

    host: str = "0.0.0.0"
    port: int = 8090
    reload: bool = False
    audit_url: str = Field(default_factory=lambda: os.getenv("AEGIS_AUDIT_URL", ""))
    emit_audit: bool = Field(
        default_factory=lambda: os.getenv("AEGIS_AUDIT_EMIT", "true").lower() != "false"
    )


settings = Settings()
