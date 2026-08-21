"""Editing your own profile and changing your own password.

Both endpoints act on the caller and nobody else -- neither takes an id, so
there is no way to aim them at another account.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import RefreshToken, User

PASSWORD = "mật-khẩu-đủ-dài"
NEW_PASSWORD = "mật-khẩu-mới-dài"
EMAIL = "hoc.vien@example.com"

PROFILE = "/api/v1/users/me"
PASSWORD_URL = "/api/v1/users/me/password"
COOKIE = get_settings().refresh_cookie_name


async def sign_in(
    client: AsyncClient, session: AsyncSession, **overrides
) -> dict[str, str]:
    """Create an account, sign in, and return the Authorization header."""
    fields = {
        "email": EMAIL,
        "full_name": "Học Viên A",
        "password_hash": hash_password(PASSWORD),
        **overrides,
    }
    session.add(User(**fields))
    await session.flush()

    response = await client.post(
        "/api/v1/auth/login", json={"email": fields["email"], "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def user_row(session: AsyncSession, email: str = EMAIL) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    await session.refresh(user)
    return user


async def live_sessions(session: AsyncSession, user_id) -> list[RefreshToken]:
    rows = await session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    return list(rows)


# --- Profile ---------------------------------------------------------------


async def test_updating_the_name(api_client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await sign_in(api_client, db_session)

    response = await api_client.patch(
        PROFILE, json={"full_name": "Tên Mới"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Tên Mới"
    assert (await user_row(db_session)).full_name == "Tên Mới"


async def test_the_name_is_trimmed(api_client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await sign_in(api_client, db_session)

    response = await api_client.patch(
        PROFILE, json={"full_name": "  Tên Có Khoảng Trắng  "}, headers=headers
    )

    assert response.json()["full_name"] == "Tên Có Khoảng Trắng"


@pytest.mark.parametrize("name", ["", "   ", "x" * 151])
async def test_an_unusable_name_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, name: str
) -> None:
    headers = await sign_in(api_client, db_session)

    response = await api_client.patch(PROFILE, json={"full_name": name}, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


async def test_the_profile_endpoint_cannot_change_role_or_email(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Mass assignment: the only field this endpoint knows about is the name.

    An email change needs the new address proven before it is trusted, which is
    a flow of its own, not a field in this form.
    """
    headers = await sign_in(api_client, db_session)

    await api_client.patch(
        PROFILE,
        json={"full_name": "Tên Mới", "role": "admin", "email": "khac@example.com"},
        headers=headers,
    )

    user = await user_row(db_session)
    assert user.role == "student"
    assert user.email == EMAIL


async def test_editing_a_profile_requires_signing_in(api_client: AsyncClient) -> None:
    response = await api_client.patch(PROFILE, json={"full_name": "Ai Đó"})

    assert response.status_code == 401


# --- Password --------------------------------------------------------------


async def test_changing_the_password(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(api_client, db_session)

    response = await api_client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 200
    assert verify_password(NEW_PASSWORD, (await user_row(db_session)).password_hash)


async def test_the_old_password_stops_working(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(api_client, db_session)
    await api_client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    old = await api_client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    new = await api_client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    )

    assert old.status_code == 401
    assert new.status_code == 200


async def test_a_wrong_current_password_is_refused(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Someone who walked up to an unlocked laptop should not get the account."""
    headers = await sign_in(api_client, db_session)

    response = await api_client.post(
        PASSWORD_URL,
        json={"current_password": "đoán-đại-thôi", "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_CURRENT_PASSWORD"
    assert verify_password(PASSWORD, (await user_row(db_session)).password_hash)


async def test_reusing_the_same_password_is_refused(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(api_client, db_session)

    response = await api_client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": PASSWORD},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PASSWORD_UNCHANGED"


@pytest.mark.parametrize("new_password", ["ngắn", "đ" * 40])
async def test_the_new_password_must_pass_the_same_rules_as_registration(
    api_client: AsyncClient, db_session: AsyncSession, new_password: str
) -> None:
    """Too short, or long enough that bcrypt would silently ignore the tail."""
    headers = await sign_in(api_client, db_session)

    response = await api_client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": new_password},
        headers=headers,
    )

    assert response.status_code == 422


async def test_a_google_only_account_has_no_password_to_change(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Nothing to verify against, so there is nothing this endpoint can do."""
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
    # Sign in the Google way: straight to a session, no password involved.
    from app.services.auth import sign_in_with_google
    from app.services.google_oauth import GoogleIdentity

    tokens = await sign_in_with_google(
        db_session,
        identity=GoogleIdentity(
            sub="sub-1",
            email="google@example.com",
            email_verified=True,
            full_name="Google Only",
            picture=None,
        ),
    )
    headers = {"Authorization": f"Bearer {tokens.access_token}"}

    response = await api_client.post(
        PASSWORD_URL,
        json={"current_password": "bất-kỳ-cái-gì", "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PASSWORD_NOT_SET"


async def test_changing_the_password_signs_other_devices_out(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The reason most people change a password is that someone else may have it."""
    headers = await sign_in(api_client, db_session)
    # A second device, signed in before the change.
    await api_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    user = await user_row(db_session)
    assert len(await live_sessions(db_session, user.id)) == 2

    await api_client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    # Exactly one session left: the one just issued to the device that changed it.
    assert len(await live_sessions(db_session, user.id)) == 1


async def test_the_device_that_changed_the_password_stays_signed_in(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(api_client, db_session)

    changed = await api_client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert changed.json()["access_token"]
    assert changed.cookies[COOKIE]
    # The new cookie is the one that works from here on.
    refreshed = await api_client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200


async def test_changing_a_password_requires_signing_in(api_client: AsyncClient) -> None:
    response = await api_client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 401
