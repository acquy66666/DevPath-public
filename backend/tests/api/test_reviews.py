"""Course reviews.

Two rules carry the file. Only someone enrolled may write a review -- the
instructor of the course included, who is refused for a different reason. And
`courses.rating_avg` / `rating_count` must agree with the rows in `reviews`
after every write, including the ones that remove or lower a rating, because
those columns are what the catalogue sorts and filters on.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Enrollment, Review, User

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


async def make_course(session: AsyncSession, owner: User) -> Course:
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title="Khóa học được đánh giá",
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()
    return course


async def enrol(session: AsyncSession, course: Course, user: User) -> None:
    session.add(Enrollment(user_id=user.id, course_id=course.id, source="free"))
    await session.flush()


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def course(db_session: AsyncSession, owner: User) -> Course:
    return await make_course(db_session, owner)


@pytest.fixture
async def student(db_session: AsyncSession, course: Course) -> User:
    user = await make_user(db_session)
    await enrol(db_session, course, user)
    return user


# --- Writing ---------------------------------------------------------------


async def test_enrolled_student_writes_a_review(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    headers = await sign_in(api_client, student)

    response = await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 5, "comment": "Giảng viên dạy rất dễ hiểu."},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rating"] == 5
    assert body["comment"] == "Giảng viên dạy rất dễ hiểu."
    assert body["author"]["id"] == str(student.id)
    # The author block is what a stranger reads; it must not carry an email.
    assert "email" not in body["author"]

    await db_session.refresh(course)
    assert course.rating_avg == Decimal("5.00")
    assert course.rating_count == 1


async def test_writing_twice_edits_the_same_review(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    """The second PUT is an edit, not a second review -- and the average follows."""
    headers = await sign_in(api_client, student)
    url = f"/api/v1/courses/{course.id}/reviews/me"

    first = await api_client.put(url, json={"rating": 5}, headers=headers)
    second = await api_client.put(
        url, json={"rating": 2, "comment": "Xem lại thì phần sau hơi sơ sài."},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]

    rows = await db_session.scalar(
        select(func.count()).select_from(Review).where(Review.course_id == course.id)
    )
    assert rows == 1

    # The point of recomputing rather than adding: a rating that went down has
    # to bring the average down with it.
    await db_session.refresh(course)
    assert course.rating_avg == Decimal("2.00")
    assert course.rating_count == 1


async def test_average_covers_every_review(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    other = await make_user(db_session)
    await enrol(db_session, course, other)

    await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 5},
        headers=await sign_in(api_client, student),
    )
    await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 4},
        headers=await sign_in(api_client, other),
    )

    await db_session.refresh(course)
    assert course.rating_avg == Decimal("4.50")
    assert course.rating_count == 2


async def test_blank_comment_is_stored_as_nothing(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    """A textarea the reader left alone is not a comment of spaces."""
    response = await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 4, "comment": "   "},
        headers=await sign_in(api_client, student),
    )

    assert response.status_code == 201, response.text
    assert response.json()["comment"] is None

    stored = await db_session.scalar(
        select(Review).where(Review.course_id == course.id)
    )
    assert stored is not None
    assert stored.comment is None


# --- Who may write ---------------------------------------------------------


async def test_review_without_enrollment_is_403(
    api_client: AsyncClient, db_session: AsyncSession, course: Course
) -> None:
    stranger = await make_user(db_session)

    response = await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 5},
        headers=await sign_in(api_client, stranger),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_ENROLLED"


async def test_instructor_cannot_review_own_course(
    api_client: AsyncClient, course: Course, owner: User
) -> None:
    response = await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 5},
        headers=await sign_in(api_client, owner),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CANNOT_REVIEW_OWN_COURSE"


async def test_review_requires_signing_in(
    api_client: AsyncClient, course: Course
) -> None:
    response = await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me", json={"rating": 5}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NOT_AUTHENTICATED"


async def test_unknown_course_is_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    student = await make_user(db_session)

    response = await api_client.put(
        f"/api/v1/courses/{uuid.uuid4()}/reviews/me",
        json={"rating": 5},
        headers=await sign_in(api_client, student),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_draft_course_is_404_rather_than_403(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Not-enrolled must not be the answer that reveals an unpublished course."""
    draft = await make_course(db_session, owner)
    draft.status = "draft"
    draft.published_at = None
    await db_session.flush()

    student = await make_user(db_session)

    response = await api_client.put(
        f"/api/v1/courses/{draft.id}/reviews/me",
        json={"rating": 5},
        headers=await sign_in(api_client, student),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


@pytest.mark.parametrize("rating", [0, 6, -1])
async def test_rating_outside_one_to_five_is_422(
    api_client: AsyncClient, course: Course, student: User, rating: int
) -> None:
    response = await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": rating},
        headers=await sign_in(api_client, student),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


# --- Reading ---------------------------------------------------------------


async def test_anyone_can_read_the_reviews(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    """No token at all: the list is part of the public course page."""
    await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 4, "comment": "Đáng học."},
        headers=await sign_in(api_client, student),
    )

    response = await api_client.get(f"/api/v1/courses/{course.id}/reviews")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["rating_avg"] == "4.00"
    assert body["rating_count"] == 1
    assert body["items"][0]["comment"] == "Đáng học."


async def test_reviews_come_back_newest_first(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    other = await make_user(db_session)
    await enrol(db_session, course, other)

    await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 3, "comment": "Đầu tiên"},
        headers=await sign_in(api_client, student),
    )
    await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 5, "comment": "Sau đó"},
        headers=await sign_in(api_client, other),
    )

    # Everything a test writes shares one transaction, and `now()` in Postgres
    # is the transaction's start time -- so both rows carry the same instant and
    # there is nothing for an ORDER BY to sort. Backdating one gives the query
    # the gap it always has outside a test.
    await db_session.execute(
        update(Review)
        .where(Review.course_id == course.id, Review.user_id == student.id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=1))
    )
    db_session.expire_all()

    body = (await api_client.get(f"/api/v1/courses/{course.id}/reviews")).json()

    assert [item["comment"] for item in body["items"]] == ["Sau đó", "Đầu tiên"]


async def test_my_review_is_404_before_writing_one(
    api_client: AsyncClient, course: Course, student: User
) -> None:
    response = await api_client.get(
        f"/api/v1/courses/{course.id}/reviews/me",
        headers=await sign_in(api_client, student),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REVIEW_NOT_FOUND"


# --- Withdrawing -----------------------------------------------------------


async def test_deleting_a_review_puts_the_rating_back(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    headers = await sign_in(api_client, student)
    url = f"/api/v1/courses/{course.id}/reviews/me"

    await api_client.put(url, json={"rating": 5}, headers=headers)
    response = await api_client.delete(url, headers=headers)

    assert response.status_code == 204

    await db_session.refresh(course)
    assert course.rating_avg == Decimal("0.00")
    assert course.rating_count == 0


async def test_deleting_a_review_that_is_not_there_is_404(
    api_client: AsyncClient, course: Course, student: User
) -> None:
    response = await api_client.delete(
        f"/api/v1/courses/{course.id}/reviews/me",
        headers=await sign_in(api_client, student),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REVIEW_NOT_FOUND"


async def test_one_person_cannot_delete_another_persons_review(
    api_client: AsyncClient, db_session: AsyncSession, course: Course, student: User
) -> None:
    """There is no address for somebody else's review, so this is the whole test:
    deleting "mine" when only theirs exists must leave theirs alone."""
    await api_client.put(
        f"/api/v1/courses/{course.id}/reviews/me",
        json={"rating": 5},
        headers=await sign_in(api_client, student),
    )

    other = await make_user(db_session)
    await enrol(db_session, course, other)

    response = await api_client.delete(
        f"/api/v1/courses/{course.id}/reviews/me",
        headers=await sign_in(api_client, other),
    )

    assert response.status_code == 404

    remaining = await db_session.scalar(
        select(func.count()).select_from(Review).where(Review.course_id == course.id)
    )
    assert remaining == 1
