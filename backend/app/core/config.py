import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Fine for development, refused in production by the validator below.
DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


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

    # Auth. Short access token because it cannot be revoked; long refresh token
    # because it can (rotation + revocation live in refresh_tokens).
    jwt_secret: str = DEV_JWT_SECRET
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    refresh_cookie_name: str = "devpath_refresh"

    # Google OAuth. Empty until someone registers an OAuth client in Google
    # Cloud Console; `google_oauth_enabled` is what the routes check.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Phase 5 replaces this with a real admin review queue; until then a
    # submitted course goes straight to published so the rest of Phase 2 has
    # something to show.
    auto_approve_courses: bool = True

    # Where the browser lands after the OAuth round trip.
    frontend_url: str = "http://localhost:3000"

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

    @model_validator(mode="after")
    def reject_the_dev_secret_in_production(self) -> "Settings":
        """A shipped default signing key would let anyone mint admin tokens."""
        if self.env == "production" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set to a real secret when ENV=production")
        return self

    @property
    def google_oauth_enabled(self) -> bool:
        """Both halves or neither -- a client id without its secret cannot sign in."""
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def cookie_secure(self) -> bool:
        """Refresh cookie is HTTPS-only everywhere except local development."""
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once per process."""
    return Settings()
