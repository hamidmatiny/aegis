"""Service configuration from environment."""

from pydantic import Field, model_validator
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
    audit_service_url: str = Field(
        default="http://localhost:8084",
        validation_alias="AUDIT_SERVICE_URL",
    )
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
    chat_model_walkthrough: str = Field(
        default="",
        validation_alias="SMB_CHAT_MODEL_WALKTHROUGH",
        description="Paid walkthrough model; falls back to SMB_CHAT_MODEL when unset.",
    )
    qa_max_tokens_free: int = Field(default=500, validation_alias="SMB_QA_MAX_TOKENS_FREE")
    qa_max_tokens_walkthrough: int = Field(
        default=1200,
        validation_alias="SMB_QA_MAX_TOKENS_WALKTHROUGH",
    )
    qa_top_k: int = Field(default=5, validation_alias="SMB_QA_TOP_K")
    qa_rate_limit: int = Field(default=5, validation_alias="SMB_QA_RATE_LIMIT")
    qa_rate_window_sec: int = Field(default=60, validation_alias="SMB_QA_RATE_WINDOW_SEC")
    host: str = Field(default="0.0.0.0", validation_alias="SMB_COPILOT_HOST")
    port: int = Field(default=8093, validation_alias="SMB_COPILOT_PORT")
    session_secret: str = Field(
        default="dev-insecure-session-secret-change-me",
        validation_alias="SMB_SESSION_SECRET",
    )
    cookie_secure: bool = Field(default=False, validation_alias="SMB_COOKIE_SECURE")
    cookie_path: str = Field(default="/", validation_alias="SMB_COOKIE_PATH")
    admin_username: str = Field(default="", validation_alias="ADMIN_USERNAME")
    admin_password_hash: str = Field(default="", validation_alias="ADMIN_PASSWORD_HASH")

    @model_validator(mode="after")
    def default_walkthrough_model(self) -> Settings:
        if not self.chat_model_walkthrough.strip():
            object.__setattr__(self, "chat_model_walkthrough", self.chat_model)
        return self


settings = Settings()
