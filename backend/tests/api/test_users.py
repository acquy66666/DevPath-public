"""Becoming an instructor.

Anyone with an account can do this to themselves -- teaching is opt-in, not
something an admin has to grant. The rules worth testing are what it must not
do: touch anyone else's account, and take a role away from an admin.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User

PASSWORD = "mật-khẩu-đủ-dài"
BECOME_INSTRUCTOR = "/api/v1/users/me/instructor"


async def signed_in_as(
    client: AsyncClient, session: AsyncSession, role: str
) -> dict[str, str]:
    email = f"{role}@example.com"
    session.add(
        User(
            email=email,
            full_name=role.title(),
            password_hash=hash_password(PASSWORD),
            role=role,
        )
    )
    await session.flush()

    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def role_of(session: AsyncSession, email: str) -> str:
    user = await session.scalar(select(User).where(User.email == email))
    await session.refresh(user)
    return user.role


async def test_a_student_can_become_an_instructor(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await signed_in_as(api_client, db_session, "student")

    response = await api_client.post(BECOME_INSTRUCTOR, headers=headers)

    assert response.status_code == 200
    assert response.json()["role"] == "instructor"
    assert await role_of(db_session, "student@example.com") == "instructor"


async def test_becoming_an_instructor_changes_nothing_else(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await signed_in_as(api_client, db_session, "student")

    body = (await api_client.post(BECOME_INSTRUCTOR, headers=headers)).json()

    assert body["email"] == "student@example.com"
    assert body["full_name"] == "Student"


async def test_asking_twice_is_not_an_error(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Two tabs, two clicks. The second one already has what it asked for."""
    headers = await signed_in_as(api_client, db_session, "student")
    await api_client.post(BECOME_INSTRUCTOR, headers=headers)

    response = await api_client.post(BECOME_INSTRUCTOR, headers=headers)

    assert response.status_code == 200
    assert response.json()["role"] == "instructor"


async def test_an_admin_is_not_quietly_demoted(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """`instructor` is not a superset of `admin`, so this would take away
    rights. Refuse loudly rather than answer 200 and change nothing."""
    headers = await signed_in_as(api_client, db_session, "admin")

    response = await api_client.post(BECOME_INSTRUCTOR, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ROLE_CHANGE_NOT_ALLOWED"
    assert await role_of(db_session, "admin@example.com") == "admin"


async def test_signing_in_is_required(api_client: AsyncClient) -> None:
    response = await api_client.post(BECOME_INSTRUCTOR)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize("header", ["Bearer nonsense", "Basic abc"])
async def test_a_bad_token_cannot_promote_anyone(
    api_client: AsyncClient, header: str
) -> None:
    response = await api_client.post(BECOME_INSTRUCTOR, headers={"Authorization": header})

    assert response.status_code == 401


async def test_the_next_refresh_carries_the_new_role(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The access token holds a snapshot of the role from the moment it was
    issued, so the frontend refreshes to see itself as an instructor."""
    headers = await signed_in_as(api_client, db_session, "student")
    await api_client.post(BECOME_INSTRUCTOR, headers=headers)

    refreshed = await api_client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["user"]["role"] == "instructor"


async def test_promotion_touches_only_the_caller(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add(
        User(
            email="nguoi.khac@example.com",
            full_name="Người Khác",
            password_hash=hash_password(PASSWORD),
        )
    )
    headers = await signed_in_as(api_client, db_session, "student")

    await api_client.post(BECOME_INSTRUCTOR, headers=headers)

    assert await role_of(db_session, "nguoi.khac@example.com") == "student"
