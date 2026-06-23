"""Service configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_INPUT_DEFENSE_")

    host: str = "0.0.0.0"
    port: int = 8090
    reload: bool = False


settings = Settings()
