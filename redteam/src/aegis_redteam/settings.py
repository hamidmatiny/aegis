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
    adaptive_rounds: int = 3
    adaptive_max_rounds: int = 5
    adaptive_max_variants_per_bypass: int = 4
    model_router_url: str = Field(
        default_factory=lambda: os.getenv("AEGIS_MODEL_ROUTER_URL", "http://localhost:8082")
    )
    router_provider: str = "grok"
    router_model: str = "grok-4.3"
    router_timeout: float = 60.0
    router_max_retries: int = 3
    use_router_mutations: bool = True
    max_router_blocked: int = 15
    max_router_bypass: int = 5


settings = Settings()
