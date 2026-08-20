import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_parses_comma_separated_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose passes CORS_ORIGINS as plain text, not JSON.

    pydantic-settings JSON-decodes complex fields straight out of the
    environment, so without opting out of that decoding the container dies at
    import time -- a failure the host never sees, because a missing .env means
    the default list is used and nothing is ever parsed.
    """
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,https://devpath.vn")

    settings = Settings()

    assert settings.cors_origins == ["http://localhost:3000", "https://devpath.vn"]


def test_cors_origins_accepts_a_single_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    settings = Settings()

    assert settings.cors_origins == ["http://localhost:3000"]


def test_cors_origins_still_accepts_a_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """The .env.example format may change; both spellings must keep working."""
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')

    settings = Settings()

    assert settings.cors_origins == ["http://localhost:3000"]


def test_production_refuses_to_start_on_the_default_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shipped signing key would let anyone mint themselves an admin token."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_production_starts_with_a_real_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-from-the-vps-env-file")

    assert Settings().jwt_secret == "a-real-secret-from-the-vps-env-file"


def test_refresh_cookie_is_https_only_in_production_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Secure cookies never arrive over plain http, which is all localhost has."""
    monkeypatch.setenv("ENV", "development")
    assert Settings().cookie_secure is False

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-from-the-vps-env-file")
    assert Settings().cookie_secure is True
