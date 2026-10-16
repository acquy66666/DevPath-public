"""How many upload URLs one account may ask for, and how many bytes.

Since 16/10 a signed URL takes exactly the bytes it was signed for, so what one
account can write into the bucket is the sum of the tickets it was handed. On
the VPS that bucket shares a disk with Postgres, and a ticket nobody confirms
stays there until the orphan sweep -- one day plus fourteen of quarantine. So
the count is kept where the tickets are handed out, before anything is signed.

The limiter here is the in-memory one with a clock the test moves itself, and
the limits are shrunk to numbers a test can reach. The real numbers, and why
they are what they are, live with the settings.
"""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import VideoAsset
from app.services.rate_limit import get_rate_limiter
from app.services.storage import get_storage
from app.services.tasks import get_task_queue
from app.services.upload_limits import (
    AVATAR_WINDOW_SECONDS,
    VIDEO_BYTES_WINDOW_SECONDS,
    VIDEO_TICKET_WINDOW_SECONDS,
)
from tests.api.fakes import FakeQueue, FakeStorage, MemoryRateLimiter
from tests.api.publishing import admin_headers
from tests.api.test_avatar import avatar_body
from tests.api.test_video_upload import make_lesson, make_user, sign_in, upload_body

MB = 1024 * 1024
AVATARS = "/api/v1/users/me/avatar"


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
def queue(app: FastAPI) -> FakeQueue:
    fake = FakeQueue()
    app.dependency_overrides[get_task_queue] = lambda: fake
    return fake


@pytest.fixture
def limiter(app: FastAPI, api_client: AsyncClient) -> MemoryRateLimiter:
    """Installed after `api_client`, so it replaces the allow-all default."""
    memory = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: memory
    return memory


@pytest.fixture
def small_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "avatar_upload_tickets_per_user", 2)
    monkeypatch.setattr(settings, "video_upload_tickets_per_user", 3)
    monkeypatch.setattr(settings, "video_upload_bytes_per_user", 100 * MB)


def assert_limited(response) -> None:
    assert response.status_code == 429, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "UPLOAD_RATE_LIMITED"
    assert detail["retry_after"] > 0
    assert int(response.headers["Retry-After"]) == detail["retry_after"]


def video_url(lesson) -> str:
    return f"/api/v1/lessons/{lesson.id}/video"


# --- Avatars: any signed-in account ----------------------------------------


@pytest.mark.usefixtures("small_limits", "limiter")
async def test_avatar_tickets_stop_at_the_limit_and_nothing_more_is_signed(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    learner = await make_user(db_session, "student")
    headers = await sign_in(api_client, learner)

    for _ in range(2):
        response = await api_client.post(AVATARS, json=avatar_body(), headers=headers)
        assert response.status_code == 201, response.text

    assert_limited(await api_client.post(AVATARS, json=avatar_body(), headers=headers))
    # Counted before signing: the refused request left no URL behind it.
    assert len(storage.signed) == 2


@pytest.mark.usefixtures("small_limits", "storage")
async def test_an_avatar_ticket_can_be_asked_for_again_once_the_window_is_over(
    api_client: AsyncClient, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    learner = await make_user(db_session, "student")
    headers = await sign_in(api_client, learner)
    for _ in range(2):
        await api_client.post(AVATARS, json=avatar_body(), headers=headers)
    assert_limited(await api_client.post(AVATARS, json=avatar_body(), headers=headers))

    limiter.now += AVATAR_WINDOW_SECONDS

    response = await api_client.post(AVATARS, json=avatar_body(), headers=headers)
    assert response.status_code == 201, response.text


@pytest.mark.usefixtures("small_limits", "storage", "limiter")
async def test_one_accounts_avatar_limit_is_not_anyone_elses(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await sign_in(api_client, await make_user(db_session, "student"))
    second = await sign_in(api_client, await make_user(db_session, "student"))
    for _ in range(2):
        await api_client.post(AVATARS, json=avatar_body(), headers=first)
    assert_limited(await api_client.post(AVATARS, json=avatar_body(), headers=first))

    response = await api_client.post(AVATARS, json=avatar_body(), headers=second)
    assert response.status_code == 201, response.text


# --- Videos: the course's instructor, by count and by bytes -----------------


@pytest.mark.usefixtures("small_limits", "limiter", "queue")
async def test_video_tickets_stop_at_the_hourly_count(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    small = upload_body(size_bytes=1 * MB)

    for _ in range(3):
        response = await api_client.post(video_url(lesson), json=small, headers=headers)
        assert response.status_code == 201, response.text

    assert_limited(await api_client.post(video_url(lesson), json=small, headers=headers))
    assert len(storage.signed) == 3


@pytest.mark.usefixtures("small_limits", "limiter", "queue")
async def test_video_tickets_stop_when_the_declared_bytes_would_pass_the_budget(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """A count alone does not protect a disk from a 2 GB ticket: sixty of them
    an hour is more than the VPS has. The bytes the tickets were signed for are
    what fills it, so those are what the budget counts."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    first = await api_client.post(
        video_url(lesson), json=upload_body(size_bytes=60 * MB), headers=headers
    )
    assert first.status_code == 201, first.text

    assert_limited(
        await api_client.post(
            video_url(lesson), json=upload_body(size_bytes=60 * MB), headers=headers
        )
    )

    # The refused 60 MB was never granted, so it was not spent: a file that
    # still fits in what is left goes through.
    fits = await api_client.post(
        video_url(lesson), json=upload_body(size_bytes=40 * MB), headers=headers
    )
    assert fits.status_code == 201, fits.text
    assert [signed.size_bytes for signed in storage.signed] == [60 * MB, 40 * MB]


@pytest.mark.usefixtures("small_limits", "storage", "queue")
async def test_video_tickets_can_be_asked_for_again_once_each_window_is_over(
    api_client: AsyncClient, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    small = upload_body(size_bytes=1 * MB)

    for _ in range(3):
        await api_client.post(video_url(lesson), json=small, headers=headers)
    assert_limited(await api_client.post(video_url(lesson), json=small, headers=headers))

    limiter.now += VIDEO_TICKET_WINDOW_SECONDS
    response = await api_client.post(video_url(lesson), json=small, headers=headers)
    assert response.status_code == 201, response.text

    big = upload_body(size_bytes=97 * MB)  # 4 MB already spent, 100 MB budget
    assert_limited(await api_client.post(video_url(lesson), json=big, headers=headers))

    limiter.now += VIDEO_BYTES_WINDOW_SECONDS
    response = await api_client.post(video_url(lesson), json=big, headers=headers)
    assert response.status_code == 201, response.text


@pytest.mark.usefixtures("limiter", "queue")
async def test_a_refused_video_ticket_leaves_the_current_video_alone(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asking for a ticket replaces the lesson's video. A refusal must happen
    before that, or a 429 would cost the instructor the video they had."""
    monkeypatch.setattr(get_settings(), "video_upload_tickets_per_user", 1)
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    first = await api_client.post(video_url(lesson), json=upload_body(), headers=headers)
    current = uuid.UUID(first.json()["video_asset_id"])

    assert_limited(
        await api_client.post(video_url(lesson), json=upload_body(), headers=headers)
    )

    await db_session.refresh(lesson)
    assert lesson.video_asset_id == current
    assert await db_session.get(VideoAsset, current) is not None
    assert storage.deleted_prefixes == []


@pytest.mark.usefixtures("limiter", "storage", "queue")
async def test_asking_for_someone_elses_lesson_does_not_spend_the_quota(
    api_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ownership is answered first, so a 403 stays a 403 rather than turning
    into a 429 -- and a refused stranger has not been handed anything to count."""
    monkeypatch.setattr(get_settings(), "video_upload_tickets_per_user", 1)
    owner = await make_user(db_session, "instructor")
    intruder = await make_user(
        db_session, "instructor", email=f"khac-{uuid.uuid4().hex[:6]}@example.com"
    )
    theirs = await make_lesson(db_session, owner)
    mine = await make_lesson(db_session, intruder)
    headers = await sign_in(api_client, intruder)

    refused = await api_client.post(video_url(theirs), json=upload_body(), headers=headers)
    assert refused.status_code in (403, 404)

    response = await api_client.post(video_url(mine), json=upload_body(), headers=headers)
    assert response.status_code == 201, response.text


# --- Banners: deliberately not limited ---------------------------------------


@pytest.mark.usefixtures("small_limits", "storage")
async def test_banner_tickets_are_not_counted(
    api_client: AsyncClient, db_session: AsyncSession, limiter: MemoryRateLimiter
) -> None:
    """The admin is the person the disk alarm wakes up. Anyone holding an
    admin session can already take every course down and lock every account;
    a ticket limit would guard one window of a house whose door is open."""
    headers = await admin_headers(api_client, db_session)

    for _ in range(5):
        response = await api_client.post(
            "/api/v1/admin/banners/upload-url",
            json={"filename": "tet.png", "content_type": "image/png", "size_bytes": 8 * MB},
            headers=headers,
        )
        assert response.status_code == 200, response.text

    assert not [key for key in limiter.used if key.startswith("upload:")]
