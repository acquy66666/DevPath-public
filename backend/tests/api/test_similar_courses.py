"""`GET /api/v1/courses/{course_id}/similar` over HTTP.

The ranking itself is proved in `tests/test_content_based.py`, on axis vectors
whose cosines can be checked by hand. What is left for this file is the
contract the course page will read: no sign-in, a card that renders without a
second request, and the two ways of having nothing to show told apart -- a
course nobody may see is a 404, a course nobody has embedded yet is an empty
block.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, User
from app.services.content_based import rebuild_embeddings
from tests.test_content_based import FakeEmbedder, axis


def url(course: Course | uuid.UUID) -> str:
    course_id = course if isinstance(course, uuid.UUID) else course.id
    return f"/api/v1/courses/{course_id}/similar"


@pytest.fixture
async def catalogue(db_session: AsyncSession) -> dict[str, Course]:
    """Three published courses, two of them about the same thing."""
    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash=hash_password("mật-khẩu-đủ-dài"),
        role="instructor",
    )
    category = Category(name="Lập trình", slug=f"lt-{uuid.uuid4().hex[:8]}")
    db_session.add_all([instructor, category])
    await db_session.flush()

    courses = {}
    for key, title in (
        ("viewed", "Python cơ bản"),
        ("near", "Python nâng cao"),
        ("far", "Thiết kế đồ họa"),
    ):
        course = Course(
            instructor_id=instructor.id,
            category_id=category.id,
            title=title,
            slug=f"{uuid.uuid4().hex[:12]}",
            subtitle="Phụ đề",
            description="Mô tả khóa học.",
            status="published",
            published_at=datetime.now(tz=UTC),
        )
        db_session.add(course)
        courses[key] = course
    await db_session.flush()
    return courses


async def embed(session: AsyncSession, courses: dict[str, Course]) -> None:
    await rebuild_embeddings(
        session,
        embedder=FakeEmbedder(
            {
                "Python cơ bản": axis(0),
                "Python nâng cao": axis(0, 1),
                "Thiết kế đồ họa": axis(5),
            }
        ),
        course_ids=[course.id for course in courses.values()],
    )


async def test_anyone_can_read_the_similar_courses_of_a_published_course(
    api_client: AsyncClient, db_session: AsyncSession, catalogue: dict[str, Course]
) -> None:
    """No sign-in: the block sits on a page search engines are meant to read."""
    await embed(db_session, catalogue)

    response = await api_client.get(url(catalogue["viewed"]), params={"limit": 5})

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["id"] for item in items] == [
        str(catalogue["near"].id),
        str(catalogue["far"].id),
    ]
    assert items[0]["score"] > items[1]["score"]


async def test_a_card_carries_what_the_page_draws_without_asking_again(
    api_client: AsyncClient, db_session: AsyncSession, catalogue: dict[str, Course]
) -> None:
    await embed(db_session, catalogue)

    response = await api_client.get(url(catalogue["viewed"]))

    card = response.json()["items"][0]
    assert card["title"] == "Python nâng cao"
    assert card["slug"] == catalogue["near"].slug
    assert card["instructor"]["full_name"] == "Giảng viên"
    assert card["category"]["name"] == "Lập trình"
    assert "price" in card and "rating_avg" in card


async def test_a_course_with_no_vector_yet_has_an_empty_block(
    api_client: AsyncClient, catalogue: dict[str, Course]
) -> None:
    """Published a minute ago, nightly batch has not run. Not an error."""
    response = await api_client.get(url(catalogue["viewed"]))

    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


async def test_an_unknown_course_is_a_404_with_the_shared_error_shape(
    api_client: AsyncClient
) -> None:
    response = await api_client.get(url(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_a_draft_course_is_a_404_rather_than_an_empty_block(
    api_client: AsyncClient, db_session: AsyncSession, catalogue: dict[str, Course]
) -> None:
    """The endpoint is public, so a course the public cannot see does not
    exist here -- and "nothing is similar" would be a different claim."""
    catalogue["viewed"].status = "draft"
    await db_session.flush()

    response = await api_client.get(url(catalogue["viewed"]))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


@pytest.mark.parametrize("limit", [0, -1, 100])
async def test_an_impossible_limit_is_refused(
    api_client: AsyncClient, catalogue: dict[str, Course], limit: int
) -> None:
    response = await api_client.get(url(catalogue["viewed"]), params={"limit": limit})

    assert response.status_code == 422
