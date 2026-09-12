"""Service configuration from environment."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://aegis:aegis_dev@localhost:5432/aegis?sslmode=disable"
    redis_url: str = Field(
        default="redis://:aegis_redis_dev@127.0.0.1:6379/0",
        validation_alias="REDIS_URL",
    )
    model_router_url: str = Field(
        default="http://localhost:8082",
        validation_alias="MODEL_ROUTER_URL",
    )
    agent_gate_url: str = Field(
        default="http://localhost:8083",
        validation_alias="AGENT_GATE_URL",
    )
    agent_gate_api_keys: str = Field(
        default="",
        validation_alias="AEGIS_AGENT_GATE_API_KEYS",
    )
    audit_service_url: str = Field(
        default="http://localhost:8084",
        validation_alias="AUDIT_SERVICE_URL",
    )
    internal_token: str = Field(default="", validation_alias="AEGIS_INTERNAL_TOKEN")
    session_secret: str = Field(
        default="dev-insecure-session-secret-change-me",
        validation_alias="SMB_SESSION_SECRET",
    )
    host: str = Field(default="0.0.0.0", validation_alias="CORP_ORCHESTRATOR_HOST")
    port: int = Field(default=8094, validation_alias="CORP_ORCHESTRATOR_PORT")
    force_mock_llm: bool = Field(default=True, validation_alias="CORP_FORCE_MOCK_LLM")
    repo_root: str = Field(default=".", validation_alias="CORP_REPO_ROOT")
    scheduler_enabled: bool = Field(default=True, validation_alias="CORP_SCHEDULER_ENABLED")
    input_defense_url: str = Field(
        default="http://localhost:8090",
        validation_alias="CORP_INPUT_DEFENSE_URL",
    )
    output_defense_url: str = Field(
        default="http://localhost:8091",
        validation_alias="CORP_OUTPUT_DEFENSE_URL",
    )
    healthz_url: str = Field(
        default="https://defenseaegis.org/api/smb/healthz",
        validation_alias="CORP_HEALTHZ_URL",
    )
    github_actions_url: str = Field(
        default="https://api.github.com/repos/hamidmatiny/aegis/actions/runs?branch=main&per_page=1",
        validation_alias="CORP_GITHUB_ACTIONS_URL",
    )


settings = Settings()
