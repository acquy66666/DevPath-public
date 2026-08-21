"""The two Google endpoints, without ever calling Google.

`get_google_oauth_client` is a FastAPI dependency, so the tests hand the routes
a fake that answers instantly and can be told to fail on demand.
"""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import STATE_COOKIE_NAME
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import User
from app.services.google_oauth import (
    GoogleAuthError,
    GoogleIdentity,
    get_google_oauth_client,
)

IDENTITY = GoogleIdentity(
    sub="google-sub-9999",
    email="google.user@example.com",
    email_verified=True,
    full_name="Google User",
    picture="https://lh3.googleusercontent.com/avatar",
)

FRONTEND = get_settings().frontend_url


class FakeGoogle:
    """Stands in for accounts.google.com. Records what it was asked for."""

    def __init__(
        self,
        identity: GoogleIdentity = IDENTITY,
        error: Exception | None = None,
    ) -> None:
        self.identity = identity
        self.error = error
        self.exchanged_codes: list[str] = []

    def authorization_url(self, *, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}&client_id=fake"

    async def exchange_code(self, *, code: str) -> GoogleIdentity:
        self.exchanged_codes.append(code)
        if self.error is not None:
            raise self.error
        return self.identity


@pytest.fixture
def google(app: FastAPI) -> FakeGoogle:
    fake = FakeGoogle()
    app.dependency_overrides[get_google_oauth_client] = lambda: fake
    return fake


def query_of(location: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(location).query)


async def start_flow(client: AsyncClient) -> str:
    """Run the authorize step and return the state the backend chose."""
    response = await client.get("/api/v1/auth/google/authorize")
    return query_of(response.headers["location"])["state"][0]


# --- Authorize -------------------------------------------------------------


async def test_authorize_redirects_to_google(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    response = await api_client.get("/api/v1/auth/google/authorize")

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://accounts.google.com/")


async def test_authorize_remembers_its_state_in_a_cookie(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    """The cookie is the other half of the CSRF check on the way back."""
    response = await api_client.get("/api/v1/auth/google/authorize")

    state_in_url = query_of(response.headers["location"])["state"][0]
    assert response.cookies[STATE_COOKIE_NAME] == state_in_url
    assert "HttpOnly" in response.headers["set-cookie"]


async def test_every_authorize_picks_a_fresh_state(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    """A predictable state would be no protection at all."""
    states = {await start_flow(api_client) for _ in range(5)}

    assert len(states) == 5


async def test_authorize_is_unavailable_when_google_is_not_configured(
    api_client: AsyncClient,
) -> None:
    """No override here: the test settings have no client id, as a fresh
    checkout does."""
    response = await api_client.get("/api/v1/auth/google/authorize")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "GOOGLE_OAUTH_NOT_CONFIGURED"


# --- Callback: the happy path ----------------------------------------------


async def test_callback_signs_the_user_in_and_returns_them_to_the_frontend(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    state = await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "google-code", "state": state}
    )

    assert response.status_code == 307
    assert response.headers["location"].startswith(FRONTEND)
    assert "loi=" not in response.headers["location"]
    assert google.exchanged_codes == ["google-code"]


async def test_callback_sets_the_refresh_cookie(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    """No token travels in the URL: the SPA picks the session up by refreshing."""
    state = await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": state}
    )

    assert response.cookies[get_settings().refresh_cookie_name]


async def test_the_session_from_the_callback_actually_works(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    state = await start_flow(api_client)
    await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": state}
    )

    refreshed = await api_client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["user"]["email"] == IDENTITY.email


async def test_callback_creates_the_account(
    api_client: AsyncClient, google: FakeGoogle, db_session: AsyncSession
) -> None:
    state = await start_flow(api_client)

    await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": state}
    )

    user = await db_session.scalar(select(User).where(User.email == IDENTITY.email))
    assert user is not None
    assert user.oauth_sub == IDENTITY.sub


async def test_callback_clears_the_state_cookie(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    """One state, one use."""
    state = await start_flow(api_client)

    await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": state}
    )

    assert not api_client.cookies.get(STATE_COOKIE_NAME)


# --- Callback: everything that can go wrong --------------------------------


async def test_callback_without_a_state_cookie_is_refused(
    api_client: AsyncClient, google: FakeGoogle, db_session: AsyncSession
) -> None:
    """A callback nobody here started -- the shape of a CSRF attempt."""
    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": "made-up"}
    )

    assert response.status_code == 307
    assert query_of(response.headers["location"])["loi"] == ["GOOGLE_STATE_INVALID"]
    assert google.exchanged_codes == []
    assert await db_session.scalar(select(User).where(User.email == IDENTITY.email)) is None


async def test_callback_with_a_mismatched_state_is_refused(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback",
        params={"code": "c", "state": "not-the-state-we-issued"},
    )

    assert query_of(response.headers["location"])["loi"] == ["GOOGLE_STATE_INVALID"]
    assert google.exchanged_codes == []


async def test_callback_without_a_code_is_refused(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    state = await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"state": state}
    )

    assert query_of(response.headers["location"])["loi"] == ["GOOGLE_AUTH_FAILED"]


async def test_a_refused_consent_screen_comes_back_as_a_message(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    """Google sends ?error=access_denied when the user presses Cancel."""
    state = await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback",
        params={"error": "access_denied", "state": state},
    )

    assert query_of(response.headers["location"])["loi"] == ["GOOGLE_ACCESS_DENIED"]


async def test_a_failed_exchange_comes_back_as_a_message(
    api_client: AsyncClient, app: FastAPI
) -> None:
    fake = FakeGoogle(error=GoogleAuthError("Google từ chối mã đăng nhập"))
    app.dependency_overrides[get_google_oauth_client] = lambda: fake
    state = await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "stale", "state": state}
    )

    assert query_of(response.headers["location"])["loi"] == ["GOOGLE_AUTH_FAILED"]


async def test_an_unverified_google_email_comes_back_as_a_message(
    api_client: AsyncClient, app: FastAPI
) -> None:
    fake = FakeGoogle(
        identity=GoogleIdentity(
            sub="s", email="chua.xac.thuc@example.com", email_verified=False,
            full_name=None, picture=None,
        )
    )
    app.dependency_overrides[get_google_oauth_client] = lambda: fake
    state = await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": state}
    )

    assert query_of(response.headers["location"])["loi"] == ["GOOGLE_EMAIL_NOT_VERIFIED"]


async def test_a_locked_account_comes_back_as_a_message(
    api_client: AsyncClient, google: FakeGoogle, db_session: AsyncSession
) -> None:
    db_session.add(
        User(
            email=IDENTITY.email,
            full_name="Bị Khóa",
            password_hash=hash_password("mật-khẩu-cũ-dài"),
            locked_at=datetime.now(tz=UTC),
        )
    )
    await db_session.flush()
    state = await start_flow(api_client)

    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": state}
    )

    assert query_of(response.headers["location"])["loi"] == ["ACCOUNT_LOCKED"]


async def test_the_error_redirect_goes_to_the_sign_in_page(
    api_client: AsyncClient, google: FakeGoogle
) -> None:
    """A failed sign-in should leave the user somewhere they can try again."""
    response = await api_client.get(
        "/api/v1/auth/google/callback", params={"code": "c", "state": "made-up"}
    )

    assert response.headers["location"].startswith(f"{FRONTEND}/dang-nhap")
