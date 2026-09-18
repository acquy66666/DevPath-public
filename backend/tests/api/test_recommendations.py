"""`GET /api/v1/recommendations` over HTTP.

The service's own tests cover which rows survive the re-check against the
database. What is left for this file is the contract the frontend will read:
sign-in is required, a card carries enough to render without a second request,
and the two kinds of empty are distinguishable in the payload.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Enrollment, User
from app.services.recommendations import (
    CachedList,
    CachedRecommendation,
    get_recommendation_cache,
)
from tests.api.fakes import MemoryRecommendationCache

PASSWORD = "mật-khẩu-đủ-dài"
URL = "/api/v1/recommendations"


async def make_user(session: AsyncSession, role: str) -> User:
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
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def cache(app: FastAPI) -> MemoryRecommendationCache:
    """The cache the endpoint reads, in memory and under the test's control."""
    fake = MemoryRecommendationCache()
    app.dependency_overrides[get_recommendation_cache] = lambda: fake
    return fake


@pytest.fixture
async def catalogue(db_session: AsyncSession) -> dict:
    instructor = await make_user(db_session, "instructor")
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()

    courses = {}
    for name in ("history", "suggested"):
        course = Course(
            instructor_id=instructor.id,
            category_id=category.id,
            title=f"Khóa {name}",
            slug=f"khoa-{name}-{uuid.uuid4().hex[:8]}",
            price=Decimal("299000"),
            status="published",
            published_at=datetime.now(UTC),
        )
        db_session.add(course)
        courses[name] = course
    await db_session.flush()
    return {"instructor": instructor, "category": category, **courses}


@pytest.fixture
async def reader(db_session: AsyncSession, catalogue: dict) -> User:
    """A student who has taken the course that will be quoted as the reason."""
    user = await make_user(db_session, "student")
    db_session.add(Enrollment(user_id=user.id, course_id=catalogue["history"].id))
    await db_session.flush()
    return user


async def test_signing_in_is_required(api_client: AsyncClient, cache):
    response = await api_client.get(URL)
    assert response.status_code == 401


async def test_a_new_account_is_told_nothing_has_been_computed_yet(
    api_client: AsyncClient, cache, reader: User
):
    """`generated_at: null` is the signal the hybrid of a later task answers
    with popular courses. An empty list on its own would not say whether the
    model had run."""
    response = await api_client.get(URL, headers=await sign_in(api_client, reader))

    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "generated_at": None}


async def test_a_cached_list_comes_back_as_cards_with_a_reason(
    api_client: AsyncClient, cache, reader: User, catalogue: dict
):
    ran_at = datetime.now(UTC) - timedelta(hours=5)
    cache.write(
        reader.id,
        CachedList(
            generated_at=ran_at,
            items=[
                CachedRecommendation(
                    course_id=catalogue["suggested"].id,
                    score=1.75,
                    because=catalogue["history"].id,
                )
            ],
        ),
    )

    response = await api_client.get(URL, headers=await sign_in(api_client, reader))

    assert response.status_code == 200, response.text
    body = response.json()
    assert datetime.fromisoformat(body["generated_at"]) == ran_at

    [card] = body["items"]
    assert card["id"] == str(catalogue["suggested"].id)
    assert card["score"] == 1.75
    assert card["because"] == {
        "id": str(catalogue["history"].id),
        "title": catalogue["history"].title,
        "slug": catalogue["history"].slug,
    }
    # Enough to draw the card without a second request per course.
    assert card["instructor"]["full_name"] == catalogue["instructor"].full_name
    assert card["category"]["slug"] == catalogue["category"].slug
    # Compared as a number: the string carries however many decimal places the
    # value was read with, which differs between a fresh read of NUMERIC(12,2)
    # and the object still in this session's identity map.
    assert Decimal(card["price"]) == Decimal("299000")


async def test_a_card_carries_no_answer_to_a_question_it_was_not_asked(
    api_client: AsyncClient, cache, reader: User, catalogue: dict
):
    """A recommendation is a catalogue card, not the whole course row: no
    description, no status, nothing about the instructor beyond their name."""
    cache.write(
        reader.id,
        CachedList(
            generated_at=datetime.now(UTC),
            items=[
                CachedRecommendation(
                    course_id=catalogue["suggested"].id,
                    score=1.0,
                    because=catalogue["history"].id,
                )
            ],
        ),
    )

    response = await api_client.get(URL, headers=await sign_in(api_client, reader))

    [card] = response.json()["items"]
    assert "description" not in card
    assert "status" not in card


async def test_limit_is_honoured_and_bounded(
    api_client: AsyncClient, cache, reader: User, catalogue: dict
):
    cache.write(
        reader.id,
        CachedList(
            generated_at=datetime.now(UTC),
            items=[
                CachedRecommendation(
                    course_id=catalogue["suggested"].id,
                    score=1.0,
                    because=catalogue["history"].id,
                )
            ],
        ),
    )
    headers = await sign_in(api_client, reader)

    assert len((await api_client.get(f"{URL}?limit=1", headers=headers)).json()["items"]) == 1
    # Above what the batch stores: answering it would return fewer than asked
    # and look like a bug in the model rather than a bad request.
    assert (await api_client.get(f"{URL}?limit=999", headers=headers)).status_code == 422
    assert (await api_client.get(f"{URL}?limit=0", headers=headers)).status_code == 422


async def test_one_reader_s_cache_is_not_another_s(
    api_client: AsyncClient, cache, db_session: AsyncSession, reader: User, catalogue: dict
):
    cache.write(
        reader.id,
        CachedList(
            generated_at=datetime.now(UTC),
            items=[
                CachedRecommendation(
                    course_id=catalogue["suggested"].id,
                    score=1.0,
                    because=catalogue["history"].id,
                )
            ],
        ),
    )
    stranger = await make_user(db_session, "student")

    response = await api_client.get(URL, headers=await sign_in(api_client, stranger))

    assert response.json() == {"items": [], "generated_at": None}
