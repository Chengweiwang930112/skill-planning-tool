from functools import lru_cache
from pathlib import Path
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
    database_url: str = "postgresql+psycopg://skills:skills@localhost:5432/skills"
    # The built frontend, served alongside the API; the container image sets it.
    static_dir: Path | None = None

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
