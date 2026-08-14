"""SDK configuration from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_", extra="ignore")

    input_defense_url: str = "http://localhost:8090"
    output_defense_url: str = "http://localhost:8091"
    policy_engine_url: str = "http://localhost:8081"
    model_router_url: str = "http://localhost:8082"
    agent_gate_url: str = "http://localhost:8083"
    # Comma-separated; embedded mode uses the first value as the service
    # key sent to agent-gate's POST /v1/evaluate. Never used for deciding
    # an approval — that requires a separate reviewer key, held by an
    # actual human via the dashboard, not by SDK/agent code.
    agent_gate_api_keys: str = ""
    # AEGIS_INTERNAL_TOKEN -- required in embedded/direct mode (base_url
    # unset) since input-defense/output-defense/policy-engine/model-router
    # all enforce this shared internal token; unused in proxy mode (the
    # gateway handles its own auth, this SDK just forwards api_key to it).
    internal_token: str = ""
    sdk_proxy_host: str = "0.0.0.0"
    sdk_proxy_port: int = 8080
    default_tenant_id: str = "default"
    default_model: str = "mock-model"


settings = Settings()
