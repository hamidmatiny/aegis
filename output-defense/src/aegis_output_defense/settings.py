"""Service configuration."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aegis_output_defense.ml.loader import SPACY_MODEL_NAME, TOXIC_BERT_MODEL_ID


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_OUTPUT_DEFENSE_")

    host: str = "0.0.0.0"
    port: int = 8091
    reload: bool = False
    audit_url: str = Field(default_factory=lambda: os.getenv("AEGIS_AUDIT_URL", ""))
    emit_audit: bool = Field(
        default_factory=lambda: os.getenv("AEGIS_AUDIT_EMIT", "true").lower() != "false"
    )

    # Detector backends — production defaults use real models / model-router.
    toxicity_backend: Literal["stub", "toxic-bert"] = "toxic-bert"
    pii_backend: Literal["regex", "ner"] = "ner"
    backtranslation_backend: Literal["stub", "router"] = "router"
    judge_backend: Literal["stub", "router"] = "router"

    toxic_bert_model_id: str = TOXIC_BERT_MODEL_ID
    spacy_model: str = SPACY_MODEL_NAME
    warmup_on_start: bool = False

    model_router_url: str = Field(
        default_factory=lambda: os.getenv("AEGIS_MODEL_ROUTER_URL", "http://localhost:8082")
    )
    backtranslation_model: str = Field(
        default_factory=lambda: os.getenv(
            "AEGIS_OUTPUT_DEFENSE_BACKTRANSLATION_MODEL", "mock-model"
        )
    )
    judge_model: str = Field(
        default_factory=lambda: os.getenv("AEGIS_OUTPUT_DEFENSE_JUDGE_MODEL", "mock-model")
    )
    router_timeout: float = 60.0


settings = Settings()
