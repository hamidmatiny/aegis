"""Service configuration from environment."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for smb-copilot.

    Reads ``DATABASE_URL``, ``POLICY_ENGINE_URL``, ``AUDIT_SERVICE_URL``, and
    ``MODEL_ROUTER_URL`` from the environment (pydantic-settings field names).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://aegis:aegis_dev@localhost:5432/aegis?sslmode=disable"
    policy_engine_url: str = "http://localhost:8081"
    audit_service_url: str = "http://localhost:8084"
    model_router_url: str = "http://localhost:8082"
    host: str = Field(default="0.0.0.0", validation_alias="SMB_COPILOT_HOST")
    port: int = Field(default=8093, validation_alias="SMB_COPILOT_PORT")


settings = Settings()
