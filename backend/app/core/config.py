from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "Staff & Skill Planning Tool"
    environment: Environment = "local"
    api_v1_prefix: str = "/api/v1"

    @property
    def docs_enabled(self) -> bool:

        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:

    return Settings()
