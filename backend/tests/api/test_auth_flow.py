"""Gaps left by the per-endpoint tests, plus the journey they never take.

Everything else tests one endpoint at a time. These are the cases that only
appear when two endpoints meet -- a session opened here and refused there, a
device signed out while another stays in -- and one run through the whole
sequence a person actually performs.
"""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models import RefreshToken, User
from app.services import instructor_applications as applications_service
from tests.api.publishing import make_admin

PASSWORD = "mật-khẩu-đủ-dài"
NEW_PASSWORD = "mật-khẩu-mới-dài"
EMAIL = "hoc.vien@example.com"
COOKIE = get_settings().refresh_cookie_name


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register(client: AsyncClient, email: str = EMAIL) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Học Viên A"},
    )
    return response.json()


async def live_sessions(session: AsyncSession, user_id) -> list[RefreshToken]:
    rows = await session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    return list(rows)


async def second_device(app, db_session: AsyncSession) -> AsyncClient:
    """A separate client with its own cookie jar, signed in as the same person."""
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    return client


# --- A session that outlives the reason it was granted ---------------------


async def test_a_locked_account_cannot_refresh_a_session_it_already_had(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Locking an account has to end it, not wait for it to expire.

    The refresh token was handed out before the lock and is still unexpired
    and unrevoked -- the only thing standing between it and a fresh 30 days is
    this check.
    """
    body = await register(api_client)
    user = await db_session.get(User, body["user"]["id"])
    user.locked_at = datetime.now(tz=UTC)
    await db_session.flush()

    response = await api_client.post("/api/v1/auth/refresh")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ACCOUNT_LOCKED"


async def test_a_deleted_account_cannot_use_a_token_it_still_holds(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The token stays cryptographically valid; the account behind it is gone."""
    body = await register(api_client)
    token = body["access_token"]
    await db_session.delete(await db_session.get(User, body["user"]["id"]))
    await db_session.flush()

    response = await api_client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NOT_AUTHENTICATED"


async def test_an_expired_access_token_is_refused_over_http(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The unit tests prove the decoder rejects it; this proves the endpoint does."""
    body = await register(api_client)
    expired = create_access_token(
        uuid.UUID(body["user"]["id"]), "student", expires_in=timedelta(seconds=-1)
    )

    response = await api_client.get("/api/v1/auth/me", headers=bearer(expired))

    assert response.status_code == 401


# --- One device is not every device ----------------------------------------


async def test_signing_out_ends_this_device_only(
    app, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Signing out of a library computer must not sign out the phone."""
    body = await register(api_client)
    phone = await second_device(app, db_session)
    assert len(await live_sessions(db_session, body["user"]["id"])) == 2

    await api_client.post("/api/v1/auth/logout")

    assert len(await live_sessions(db_session, body["user"]["id"])) == 1
    # And the other device can still trade its cookie for a new token.
    assert (await phone.post("/api/v1/auth/refresh")).status_code == 200
    await phone.aclose()


# --- Registration cannot be used to take over a Google account -------------


async def test_the_email_of_a_google_account_cannot_be_registered_with_a_password(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Otherwise anyone who knows the address could bolt a password onto it."""
    db_session.add(
        User(
            email="google@example.com",
            full_name="Google Only",
            password_hash=None,
            oauth_provider="google",
            oauth_sub="sub-1",
        )
    )
    await db_session.flush()

    response = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "google@example.com",
            "password": PASSWORD,
            "full_name": "Ke Khac",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EMAIL_ALREADY_REGISTERED"


# --- Cookie flags, everywhere the cookie is set ----------------------------


async def test_every_endpoint_that_sets_the_cookie_sets_the_same_flags(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Register was checked from the start; login and refresh set it too, and a
    cookie written with different flags in one place is the one that leaks."""
    responses = [
        await api_client.post(
            "/api/v1/auth/register",
            json={"email": EMAIL, "password": PASSWORD, "full_name": "Học Viên A"},
        ),
        await api_client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ),
        await api_client.post("/api/v1/auth/refresh"),
    ]

    for response in responses:
        header = response.headers["set-cookie"]
        assert COOKIE in header
        assert "HttpOnly" in header
        assert "samesite=lax" in header.lower()
        assert "Path=/api/v1/auth" in header


# --- The whole journey, once -----------------------------------------------


async def test_the_journey_from_sign_up_to_a_changed_password(
    app, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The demo script, as a test.

    Register, look at yourself, renew the session, become an instructor (apply,
    an admin approves), change the password -- and check the two things that
    should follow from that last step: other devices are out, and the new
    password is the one that works.
    """
    body = await register(api_client)
    user_id = body["user"]["id"]
    token = body["access_token"]

    me = await api_client.get("/api/v1/auth/me", headers=bearer(token))
    assert me.json()["role"] == "student"
    assert me.json()["has_password"] is True

    renewed = await api_client.post("/api/v1/auth/refresh")
    assert renewed.status_code == 200
    token = renewed.json()["access_token"]

    applied = await api_client.post(
        "/api/v1/users/me/instructor-application", json={}, headers=bearer(token)
    )
    assert applied.status_code == 201, applied.text
    admin = await make_admin(db_session)
    await applications_service.approve(db_session, uuid.UUID(applied.json()["id"]), admin)
    me = await api_client.get("/api/v1/auth/me", headers=bearer(token))
    assert me.json()["role"] == "instructor"

    phone = await second_device(app, db_session)
    assert len(await live_sessions(db_session, user_id)) == 2

    changed = await api_client.post(
        "/api/v1/users/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=bearer(token),
    )
    assert changed.status_code == 200
    # The role survived the password change; the other device did not.
    assert changed.json()["user"]["role"] == "instructor"
    assert len(await live_sessions(db_session, user_id)) == 1
    assert (await phone.post("/api/v1/auth/refresh")).status_code == 401
    await phone.aclose()

    with_old = await api_client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    with_new = await api_client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    )
    assert with_old.status_code == 401
    assert with_new.status_code == 200
