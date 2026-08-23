"""Service configuration from environment."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for smb-copilot."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://aegis:aegis_dev@localhost:5432/aegis?sslmode=disable"
    policy_engine_url: str = "http://localhost:8081"
    audit_service_url: str = "http://localhost:8084"
    model_router_url: str = "http://localhost:8082"
    internal_token: str = Field(default="", validation_alias="AEGIS_INTERNAL_TOKEN")
    embedding_provider: str = Field(default="mock", validation_alias="SMB_EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="mock-embedding",
        validation_alias="SMB_EMBEDDING_MODEL",
    )
    host: str = Field(default="0.0.0.0", validation_alias="SMB_COPILOT_HOST")
    port: int = Field(default=8093, validation_alias="SMB_COPILOT_PORT")


settings = Settings()
