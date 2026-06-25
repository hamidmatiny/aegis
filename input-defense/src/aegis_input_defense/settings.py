"""Service configuration."""

import os
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aegis_input_defense.ml.loader import PERPLEXITY_MODEL_ID, PROMPT_GUARD_MODEL_ID


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_INPUT_DEFENSE_")

    host: str = "0.0.0.0"
    port: int = 8090
    reload: bool = False
    audit_url: str = Field(default_factory=lambda: os.getenv("AEGIS_AUDIT_URL", ""))
    emit_audit: bool = Field(
        default_factory=lambda: os.getenv("AEGIS_AUDIT_EMIT", "true").lower() != "false"
    )

    # Detector backends: production defaults use local ML models.
    classifier_backend: Literal["stub", "prompt-guard"] = "prompt-guard"
    perplexity_backend: Literal["stub", "lm"] = "lm"
    prompt_guard_model_id: str = PROMPT_GUARD_MODEL_ID
    perplexity_model_id: str = PERPLEXITY_MODEL_ID
    warmup_on_start: bool = False


settings = Settings()
