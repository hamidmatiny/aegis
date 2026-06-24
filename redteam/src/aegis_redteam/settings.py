"""Service configuration."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_REDTEAM_")

    host: str = "0.0.0.0"
    port: int = 8092
    reload: bool = False
    input_defense_url: str = "http://localhost:8090"
    output_defense_url: str = "http://localhost:8091"
    detection_threshold: float = 0.50
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    store_bypasses: bool = True


settings = Settings()
