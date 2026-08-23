"""Service configuration from environment."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for smb-copilot."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://aegis:aegis_dev@localhost:5432/aegis?sslmode=disable"
    policy_engine_url: str = Field(
        default="http://localhost:8081",
        validation_alias="POLICY_ENGINE_URL",
    )
    policy_tenants_dir: str = Field(
        default="policy-engine/policies/tenants",
        validation_alias="AEGIS_POLICY_TENANTS_DIR",
        description="Writable path for per-tenant overrides.yaml (policy-engine tenants/).",
    )
    audit_service_url: str = "http://localhost:8084"
    model_router_url: str = "http://localhost:8082"
    redis_url: str = Field(
        default="redis://:aegis_redis_dev@127.0.0.1:6379/0",
        validation_alias="REDIS_URL",
    )
    internal_token: str = Field(default="", validation_alias="AEGIS_INTERNAL_TOKEN")
    embedding_provider: str = Field(default="mock", validation_alias="SMB_EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="mock-embedding",
        validation_alias="SMB_EMBEDDING_MODEL",
    )
    chat_provider: str = Field(default="mock", validation_alias="SMB_CHAT_PROVIDER")
    chat_model: str = Field(default="mock-model", validation_alias="SMB_CHAT_MODEL")
    qa_top_k: int = Field(default=5, validation_alias="SMB_QA_TOP_K")
    qa_rate_limit: int = Field(default=5, validation_alias="SMB_QA_RATE_LIMIT")
    qa_rate_window_sec: int = Field(default=60, validation_alias="SMB_QA_RATE_WINDOW_SEC")
    host: str = Field(default="0.0.0.0", validation_alias="SMB_COPILOT_HOST")
    port: int = Field(default=8093, validation_alias="SMB_COPILOT_PORT")


settings = Settings()
