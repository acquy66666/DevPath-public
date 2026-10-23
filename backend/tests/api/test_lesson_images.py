"""Pictures inside article lessons: who may ask for an upload URL, and for what.

The bucket is a fake that records what was signed; nothing here reaches a
network. What happens to a picture nobody saved is the orphan sweep's
business (`tests/test_orphans.py`), and what the chatbot reads of an article
with pictures is ingest's (`tests/test_ingest.py`).
"""

import re

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import CourseSection
from app.services.rate_limit import get_rate_limiter
from app.services.storage import MAX_LESSON_IMAGE_BYTES, get_storage
from app.services.upload_limits import LESSON_IMAGE_WINDOW_SECONDS
from tests.api.fakes import FakeStorage, MemoryRateLimiter
from tests.api.publishing import admin_headers
from tests.api.test_video_upload import make_lesson, make_user, sign_in


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


def image_body(**overrides) -> dict:
    return {"content_type": "image/png", "size_bytes": 200_000, **overrides}


def images_url(lesson) -> str:
    return f"/api/v1/lessons/{lesson.id}/images"


async def course_id_of(session: AsyncSession, lesson) -> str:
    section = await session.get(CourseSection, lesson.section_id)
    return str(section.course_id)


# --- The ticket ------------------------------------------------------------


async def test_the_instructor_gets_a_signed_url_and_the_address_to_write(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, owner)

    response = await api_client.post(images_url(lesson), json=image_body(), headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    course_id = await course_id_of(db_session, lesson)
    # One folder per course, a random name, the extension of the type.
    assert re.fullmatch(rf"lesson-images/{course_id}/[0-9a-f]{{32}}\.png", body["storage_key"])
    assert body["public_url"] == storage.public_url(body["storage_key"])
    assert body["upload_url"].startswith("https://bucket.example/")
    assert body["content_type"] == "image/png"
    assert body["expires_in"] == get_settings().upload_url_ttl_seconds


async def test_the_type_and_the_size_are_signed_in(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """The bucket refuses a PUT whose type or length differs from the ticket,
    so a 5 MB ticket cannot be spent on a 2 GB file."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, owner)

    await api_client.post(
        images_url(lesson),
        json=image_body(content_type="image/gif; charset=binary", size_bytes=1234),
        headers=headers,
    )

    key, content_type, _, size_bytes = storage.signed[-1]
    assert key.endswith(".gif")
    assert content_type == "image/gif"
    assert size_bytes == 1234


async def test_every_picture_gets_a_new_name(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, owner)

    for _ in range(2):
        await api_client.post(images_url(lesson), json=image_body(), headers=headers)

    first, second = (signed.key for signed in storage.signed)
    assert first != second


async def test_an_admin_may_add_a_picture_to_any_article(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await admin_headers(api_client, db_session)

    response = await api_client.post(images_url(lesson), json=image_body(), headers=headers)

    assert response.status_code == 201, response.text


# --- Who is refused --------------------------------------------------------


async def test_signing_in_is_required(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")

    response = await api_client.post(images_url(lesson), json=image_body())

    assert response.status_code == 401
    assert storage.signed == []


@pytest.mark.parametrize("role", ["instructor", "student"])
async def test_nobody_else_may_put_pictures_in_a_lesson(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage, role: str
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, await make_user(db_session, role))

    response = await api_client.post(images_url(lesson), json=image_body(), headers=headers)

    assert response.status_code == 403, response.text
    assert storage.signed == []


async def test_a_lesson_that_does_not_exist_is_404(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        "/api/v1/lessons/00000000-0000-0000-0000-000000000000/images",
        json=image_body(),
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LESSON_NOT_FOUND"


@pytest.mark.parametrize("lesson_type", ["video", "quiz", "code_exercise"])
async def test_only_an_article_takes_pictures(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage, lesson_type: str
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type=lesson_type)
    headers = await sign_in(api_client, owner)

    response = await api_client.post(images_url(lesson), json=image_body(), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "LESSON_NOT_ARTICLE"
    assert storage.signed == []


@pytest.mark.parametrize(
    "body",
    [
        # SVG is a document that can carry script, and the bucket serves an
        # object back with the type it was given.
        image_body(content_type="image/svg+xml"),
        image_body(content_type="text/html"),
        image_body(size_bytes=MAX_LESSON_IMAGE_BYTES + 1),
        image_body(size_bytes=0),
        {"content_type": "image/png"},
    ],
)
async def test_what_is_not_a_small_picture_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage, body: dict
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, owner)

    response = await api_client.post(images_url(lesson), json=body, headers=headers)

    assert response.status_code == 422, response.text
    assert storage.signed == []


# --- How many --------------------------------------------------------------


@pytest.fixture
def limiter(app: FastAPI, api_client: AsyncClient) -> MemoryRateLimiter:
    """Installed after `api_client`, so it replaces the allow-all default."""
    memory = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: memory
    return memory


async def test_tickets_stop_at_the_days_limit_and_come_back_after_it(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    limiter: MemoryRateLimiter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "lesson_image_upload_tickets_per_user", 2)
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, owner)

    for _ in range(2):
        response = await api_client.post(images_url(lesson), json=image_body(), headers=headers)
        assert response.status_code == 201, response.text

    refused = await api_client.post(images_url(lesson), json=image_body(), headers=headers)
    assert refused.status_code == 429
    assert refused.json()["detail"]["code"] == "UPLOAD_RATE_LIMITED"
    # Counted before signing: the refused request left no URL behind it.
    assert len(storage.signed) == 2

    limiter.now += LESSON_IMAGE_WINDOW_SECONDS
    response = await api_client.post(images_url(lesson), json=image_body(), headers=headers)
    assert response.status_code == 201, response.text
