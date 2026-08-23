"""Signing up for a free course, and the list that comes out of it.

The rule under most of these: an enrolment is the same row a payment would
write in Phase 5, so the only way to get one now is for the course to cost
nothing.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Enrollment, User

PASSWORD = "mật-khẩu-đủ-dài"


async def make_user(session: AsyncSession, role: str = "student") -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=role.title(),
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
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_course(
    session: AsyncSession,
    owner: User,
    *,
    price: str = "0",
    status: str = "published",
    title: str = "Khóa học miễn phí",
) -> Course:
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title=title,
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        price=Decimal(price),
        status=status,
        published_at=datetime.now(UTC) if status == "published" else None,
    )
    session.add(course)
    await session.flush()
    return course


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


def enroll_url(course: Course) -> str:
    return f"/api/v1/courses/{course.id}/enroll"


# --- Enrolling -------------------------------------------------------------


async def test_a_free_course_can_be_enrolled_in(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.post(enroll_url(course), headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["course_id"] == str(course.id)
    assert body["source"] == "free"
    assert body["completed_at"] is None
    # No user id on the way out: this endpoint only ever answers about you.
    assert "user_id" not in body


async def test_enrolling_raises_the_student_count(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    await api_client.post(enroll_url(course), headers=headers)

    await db_session.refresh(course)
    assert course.students_count == 1


async def test_enrolling_does_not_look_like_the_instructor_edited_the_course(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The dashboard reads `updated_at` as "last changed". A signup is not that."""
    course = await make_course(db_session, owner)
    await db_session.refresh(course)
    before = course.updated_at

    await api_client.post(enroll_url(course), headers=await sign_in(api_client, student))

    await db_session.refresh(course)
    assert course.updated_at == before
    assert course.students_count == 1


async def test_enrolling_twice_is_the_same_enrolment(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Two tabs, or a double click, state one fact twice."""
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    first = await api_client.post(enroll_url(course), headers=headers)
    second = await api_client.post(enroll_url(course), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    await db_session.refresh(course)
    assert course.students_count == 1


async def test_a_paid_course_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """The row an enrolment writes is the row a payment has to produce."""
    course = await make_course(db_session, owner, price="499000")
    headers = await sign_in(api_client, student)

    response = await api_client.post(enroll_url(course), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COURSE_NOT_FREE"

    await db_session.refresh(course)
    assert course.students_count == 0


async def test_an_instructor_does_not_enrol_in_their_own_course(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.post(enroll_url(course), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CANNOT_ENROL_OWN_COURSE"


@pytest.mark.parametrize("course_status", ["draft", "pending_review"])
async def test_an_unpublished_course_cannot_be_enrolled_in(
    api_client: AsyncClient,
    db_session: AsyncSession,
    student: User,
    owner: User,
    course_status: str,
) -> None:
    course = await make_course(db_session, owner, status=course_status)
    headers = await sign_in(api_client, student)

    response = await api_client.post(enroll_url(course), headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_an_admin_cannot_enrol_in_a_draft_they_can_see(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Seeing a draft and joining one are different permissions."""
    course = await make_course(db_session, owner, status="draft")
    admin = await make_user(db_session, "admin")
    headers = await sign_in(api_client, admin)

    response = await api_client.post(enroll_url(course), headers=headers)

    assert response.status_code == 404


async def test_enrolling_requires_signing_in(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)

    response = await api_client.post(enroll_url(course))

    assert response.status_code == 401


async def test_enrolling_in_a_course_that_does_not_exist_is_404(
    api_client: AsyncClient, db_session: AsyncSession, student: User
) -> None:
    headers = await sign_in(api_client, student)

    response = await api_client.post(
        f"/api/v1/courses/{uuid.uuid4()}/enroll", headers=headers
    )

    assert response.status_code == 404


# --- Asking whether you are enrolled ---------------------------------------


async def test_asking_about_your_own_enrolment(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.post(enroll_url(course), headers=headers)

    response = await api_client.get(
        f"/api/v1/courses/{course.id}/enrollment", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["course_id"] == str(course.id)


async def test_asking_about_an_enrolment_you_do_not_have(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.get(
        f"/api/v1/courses/{course.id}/enrollment", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ENROLLMENT_NOT_FOUND"


async def test_one_persons_enrolment_is_not_anothers(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    await api_client.post(enroll_url(course), headers=await sign_in(api_client, student))

    stranger = await make_user(db_session, "student")
    response = await api_client.get(
        f"/api/v1/courses/{course.id}/enrollment",
        headers=await sign_in(api_client, stranger),
    )

    assert response.status_code == 404


# --- "Khóa học của tôi" ----------------------------------------------------


async def test_my_courses_lists_what_i_enrolled_in(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner, title="Python cơ bản")
    headers = await sign_in(api_client, student)
    await api_client.post(enroll_url(course), headers=headers)

    response = await api_client.get("/api/v1/enrollments/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["course"]["title"] == "Python cơ bản"
    assert item["course"]["instructor"]["full_name"] == owner.full_name
    assert item["completed_at"] is None
    assert item["enrolled_at"] is not None


async def test_my_courses_shows_nobody_elses(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    course = await make_course(db_session, owner)
    await api_client.post(enroll_url(course), headers=await sign_in(api_client, student))

    stranger = await make_user(db_session, "student")
    body = (
        await api_client.get(
            "/api/v1/enrollments/me", headers=await sign_in(api_client, stranger)
        )
    ).json()

    assert body["items"] == []
    assert body["total"] == 0


async def test_my_courses_is_newest_first(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    first = await make_course(db_session, owner, title="Đăng ký trước")
    second = await make_course(db_session, owner, title="Đăng ký sau")
    headers = await sign_in(api_client, student)

    await api_client.post(enroll_url(first), headers=headers)
    await api_client.post(enroll_url(second), headers=headers)

    # Both rows carry the same `created_at`: the column defaults to `now()`,
    # which is the transaction's start time, and this whole test is one
    # transaction. Backdating one is what makes "newest first" mean anything
    # here -- in production the two calls are two transactions and two instants.
    await db_session.execute(
        update(Enrollment)
        .where(Enrollment.course_id == first.id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await db_session.flush()

    body = (await api_client.get("/api/v1/enrollments/me", headers=headers)).json()

    assert [item["course"]["title"] for item in body["items"]] == [
        "Đăng ký sau",
        "Đăng ký trước",
    ]


async def test_a_course_taken_off_sale_stays_in_my_courses(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """Deliberate, and the one place a soft-deleted course is still read."""
    course = await make_course(db_session, owner, title="Đã gỡ khỏi cửa hàng")
    headers = await sign_in(api_client, student)
    await api_client.post(enroll_url(course), headers=headers)

    async def catalogue_has_it() -> bool:
        found = (
            await api_client.get("/api/v1/courses", params={"q": "gỡ khỏi cửa hàng"})
        ).json()
        return [item["title"] for item in found["items"]] == ["Đã gỡ khỏi cửa hàng"]

    assert await catalogue_has_it()

    course.deleted_at = datetime.now(UTC)
    await db_session.flush()

    body = (await api_client.get("/api/v1/enrollments/me", headers=headers)).json()

    assert [item["course"]["title"] for item in body["items"]] == [
        "Đã gỡ khỏi cửa hàng"
    ]
    # ...while the catalogue has already forgotten it.
    assert not await catalogue_has_it()


async def test_my_courses_pages(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    headers = await sign_in(api_client, student)
    for index in range(3):
        course = await make_course(db_session, owner, title=f"Khóa {index}")
        await api_client.post(enroll_url(course), headers=headers)

    first = (
        await api_client.get(
            "/api/v1/enrollments/me", params={"page_size": 2}, headers=headers
        )
    ).json()
    second = (
        await api_client.get(
            "/api/v1/enrollments/me",
            params={"page_size": 2, "page": 2},
            headers=headers,
        )
    ).json()

    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1


async def test_my_courses_requires_signing_in(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/enrollments/me")

    assert response.status_code == 401


async def test_the_row_says_who_and_what(
    api_client: AsyncClient, db_session: AsyncSession, student: User, owner: User
) -> None:
    """A last look at the table itself, not the API's picture of it."""
    course = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.post(enroll_url(course), headers=headers)

    row = await db_session.scalar(
        select(Enrollment).where(Enrollment.user_id == student.id)
    )

    assert row is not None
    assert row.course_id == course.id
    assert row.source == "free"
    assert row.completed_at is None
