import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, read from environment or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DevPath API"
    env: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://devpath:devpath@localhost:5432/devpath"
    redis_url: str = "redis://localhost:6379/0"

    # NoDecode: without it pydantic-settings JSON-decodes list fields straight
    # from the environment and raises before the validator below ever runs.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        """Accept a comma-separated string so .env stays readable."""
        if not isinstance(value, str):
            return value

        # A JSON array is what pydantic-settings would have produced on its own;
        # keep honouring it so either spelling works in .env.
        if value.lstrip().startswith("["):
            return json.loads(value)

        return [origin.strip() for origin in value.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once per process."""
    return Settings()
