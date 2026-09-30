"""The admin's account list, and locking.

What must hold: a locked account is locked everywhere at once -- sign-in, the
access token it already holds, and every refresh token; unlocking gives
sign-in back; an admin account can never be locked; and only an admin gets
to do any of it.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Enrollment, RefreshToken, User
from tests.api.publishing import PASSWORD, make_admin

USERS = "/api/v1/admin/users"


async def make_user(session: AsyncSession, role: str = "student", name: str = "Học Viên") -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=name,
        password_hash=hash_password(PASSWORD),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def sign_in(client: AsyncClient, user: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await make_admin(db_session)


@pytest.fixture
async def admin(api_client: AsyncClient, admin_user: User) -> dict[str, str]:
    return await sign_in(api_client, admin_user)


@pytest.fixture
async def learner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student", "Người Bị Khóa")


# --- Who may ---------------------------------------------------------------


async def test_only_an_admin_lists_or_locks(
    api_client: AsyncClient, db_session: AsyncSession, learner: User
) -> None:
    assert (await api_client.get(USERS)).status_code == 401

    teacher = await make_user(db_session, "instructor")
    headers = await sign_in(api_client, teacher)
    assert (await api_client.get(USERS, headers=headers)).status_code == 403
    response = await api_client.post(f"{USERS}/{learner.id}/lock", headers=headers)
    assert response.status_code == 403

    await db_session.refresh(learner)
    assert learner.locked_at is None


# --- The list --------------------------------------------------------------


async def test_the_list_searches_filters_and_counts(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict[str, str]
) -> None:
    token = uuid.uuid4().hex[:10]
    teacher = await make_user(db_session, "instructor", f"Giảng Viên {token}")
    student = await make_user(db_session, "student", f"Học Viên {token}")
    category = Category(name="Danh mục", slug=f"dm-{token}")
    db_session.add(category)
    await db_session.flush()
    course = Course(
        instructor_id=teacher.id,
        category_id=category.id,
        title="Khóa",
        slug=f"khoa-{token}",
        status="published",
        published_at=datetime.now(tz=UTC),
    )
    db_session.add(course)
    await db_session.flush()
    db_session.add(Enrollment(user_id=student.id, course_id=course.id, source="free"))
    await db_session.flush()

    everyone = (await api_client.get(USERS, params={"q": token}, headers=admin)).json()
    teachers = (
        await api_client.get(USERS, params={"q": token, "role": "instructor"}, headers=admin)
    ).json()

    assert everyone["total"] == 2
    by_id = {item["id"]: item for item in everyone["items"]}
    assert by_id[str(teacher.id)]["courses_count"] == 1
    assert by_id[str(student.id)]["enrollments_count"] == 1
    assert by_id[str(student.id)]["email"] == student.email
    assert by_id[str(student.id)]["has_password"] is True
    assert [item["id"] for item in teachers["items"]] == [str(teacher.id)]


async def test_the_list_is_newest_first_and_filters_locked_accounts(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict[str, str]
) -> None:
    token = uuid.uuid4().hex[:10]
    older = await make_user(db_session, name=f"Cũ {token}")
    older.created_at = datetime.now(tz=UTC) - timedelta(days=3)
    newer = await make_user(db_session, name=f"Mới {token}")
    newer.locked_at = datetime.now(tz=UTC)
    await db_session.flush()

    listed = (await api_client.get(USERS, params={"q": token}, headers=admin)).json()
    locked = (
        await api_client.get(USERS, params={"q": token, "lock": "locked"}, headers=admin)
    ).json()
    active = (
        await api_client.get(USERS, params={"q": token, "lock": "active"}, headers=admin)
    ).json()

    assert [item["id"] for item in listed["items"]] == [str(newer.id), str(older.id)]
    assert [item["id"] for item in locked["items"]] == [str(newer.id)]
    assert [item["id"] for item in active["items"]] == [str(older.id)]


# --- Lock ------------------------------------------------------------------


async def test_a_locked_account_is_locked_everywhere_at_once(
    api_client: AsyncClient, db_session: AsyncSession, admin_user: User, learner: User
) -> None:
    learner_headers = await sign_in(api_client, learner)
    assert (await api_client.get("/api/v1/auth/me", headers=learner_headers)).status_code == 200

    response = await api_client.post(
        f"{USERS}/{learner.id}/lock", headers=await sign_in(api_client, admin_user)
    )

    assert response.status_code == 200, response.text
    assert response.json()["locked_at"] is not None
    # The access token it already had stops working...
    assert (await api_client.get("/api/v1/auth/me", headers=learner_headers)).status_code == 401
    # ...so does every refresh token...
    tokens = (
        await db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == learner.id))
    ).all()
    assert tokens and all(token.revoked_at is not None for token in tokens)
    # ...and signing in again.
    login = await api_client.post(
        "/api/v1/auth/login", json={"email": learner.email, "password": PASSWORD}
    )
    assert login.status_code == 403
    assert login.json()["detail"]["code"] == "ACCOUNT_LOCKED"


async def test_locking_twice_keeps_the_first_moment(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict[str, str], learner: User
) -> None:
    first = await api_client.post(f"{USERS}/{learner.id}/lock", headers=admin)
    second = await api_client.post(f"{USERS}/{learner.id}/lock", headers=admin)

    assert second.status_code == 200
    assert second.json()["locked_at"] == first.json()["locked_at"]


async def test_an_admin_cannot_be_locked_not_even_by_themselves(
    api_client: AsyncClient, db_session: AsyncSession, admin_user: User, admin: dict[str, str]
) -> None:
    other_admin = await make_admin(db_session)

    for target in (admin_user, other_admin):
        response = await api_client.post(f"{USERS}/{target.id}/lock", headers=admin)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CANNOT_LOCK_ADMIN"
        await db_session.refresh(target)
        assert target.locked_at is None


async def test_an_unknown_account_is_a_404(
    api_client: AsyncClient, admin: dict[str, str]
) -> None:
    for action in ("lock", "unlock"):
        response = await api_client.post(f"{USERS}/{uuid.uuid4()}/{action}", headers=admin)
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "USER_NOT_FOUND"


# --- Unlock ----------------------------------------------------------------


async def test_unlocking_gives_sign_in_back(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict[str, str], learner: User
) -> None:
    await api_client.post(f"{USERS}/{learner.id}/lock", headers=admin)

    response = await api_client.post(f"{USERS}/{learner.id}/unlock", headers=admin)

    assert response.status_code == 200
    assert response.json()["locked_at"] is None
    login = await api_client.post(
        "/api/v1/auth/login", json={"email": learner.email, "password": PASSWORD}
    )
    assert login.status_code == 200
