"""Handing out signed upload URLs, and what happens after the bytes land.

Nothing here talks to Cloudflare or to a broker: both are dependencies the
app declares, so the tests override them with fakes that record what was
asked of them.
"""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Category, Course, CourseSection, Lesson, User, VideoAsset
from app.services.storage import get_storage
from app.services.tasks import get_task_queue
from tests.api.fakes import FakeStorage

PASSWORD = "mật-khẩu-đủ-dài"


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[uuid.UUID] = []

    def enqueue_transcode(self, video_asset_id: uuid.UUID) -> None:
        self.enqueued.append(video_asset_id)


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


async def make_user(session: AsyncSession, role: str, email: str | None = None) -> User:
    user = User(
        email=email or f"{role}-{uuid.uuid4().hex[:8]}@example.com",
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


async def make_lesson(
    session: AsyncSession, owner: User, *, lesson_type: str = "video"
) -> Lesson:
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title="Khóa học có video",
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    lesson = Lesson(
        section_id=section.id, title="Bài 1", type=lesson_type, position=0
    )
    session.add(lesson)
    await session.flush()
    return lesson


def upload_body(**overrides) -> dict:
    return {
        "filename": "bai-giang.mp4",
        "content_type": "video/mp4",
        "size_bytes": 50 * 1024 * 1024,
        **overrides,
    }


# --- Asking for a URL ------------------------------------------------------


async def test_owner_gets_a_signed_url(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["upload_url"].startswith("https://bucket.example/")
    # The key is derived from the new asset's id, never from the filename.
    assert body["storage_key"] == f"videos/{body['video_asset_id']}/original.mp4"
    assert body["content_type"] == "video/mp4"


async def test_the_signed_content_type_matches_what_the_browser_will_send(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """R2 signs the content type in; a mismatch is rejected at upload time."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video",
        json=upload_body(content_type="video/webm", filename="quay-man-hinh.webm"),
        headers=headers,
    )

    key, content_type, expires_in = storage.signed[-1]
    assert content_type == response.json()["content_type"] == "video/webm"
    assert key.endswith(".webm")
    assert expires_in == get_settings().upload_url_ttl_seconds


async def test_the_asset_starts_as_uploading_and_is_attached_to_the_lesson(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
    )

    asset_id = uuid.UUID(response.json()["video_asset_id"])
    asset = await db_session.get(VideoAsset, asset_id)
    assert asset is not None
    assert asset.status == "uploading"

    await db_session.refresh(lesson)
    assert lesson.video_asset_id == asset_id


async def test_uploading_again_replaces_the_previous_video(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """Otherwise the lesson plays one video while the bucket pays for two."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    first = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
    )
    first_id = uuid.UUID(first.json()["video_asset_id"])

    second = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
    )
    second_id = uuid.UUID(second.json()["video_asset_id"])

    assert first_id != second_id
    assert await db_session.get(VideoAsset, first_id) is None
    assert f"videos/{first_id}" in storage.deleted_prefixes

    await db_session.refresh(lesson)
    assert lesson.video_asset_id == second_id


async def test_a_stranger_cannot_upload_to_someone_elses_lesson(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    intruder = await make_user(db_session, "instructor", email="khac@example.com")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, intruder)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"
    assert storage.signed == []


async def test_signing_requires_signing_in(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body()
    )

    assert response.status_code == 401
    assert storage.signed == []


async def test_an_article_lesson_refuses_a_video(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "LESSON_NOT_VIDEO"


async def test_a_pdf_is_not_a_video(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video",
        json=upload_body(content_type="application/pdf", filename="slide.pdf"),
        headers=headers,
    )

    assert response.status_code == 422
    assert storage.signed == []


async def test_a_file_over_the_limit_is_refused_before_it_is_uploaded(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """The point is to save the instructor the wait, not to enforce a quota."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video",
        json=upload_body(size_bytes=5 * 1024 * 1024 * 1024),
        headers=headers,
    )

    assert response.status_code == 422
    assert storage.signed == []


async def test_a_missing_lesson_is_404(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    headers = await sign_in(api_client, owner)

    response = await api_client.post(
        f"/api/v1/lessons/{uuid.uuid4()}/video", json=upload_body(), headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LESSON_NOT_FOUND"


# --- Finishing the upload --------------------------------------------------


async def start_upload(
    client: AsyncClient, lesson: Lesson, headers: dict[str, str]
) -> uuid.UUID:
    response = await client.post(
        f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
    )
    return uuid.UUID(response.json()["video_asset_id"])


async def test_completing_moves_to_processing_and_queues_the_transcode(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)

    response = await api_client.post(
        f"/api/v1/video-assets/{asset_id}/complete", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert queue.enqueued == [asset_id]


async def test_completing_twice_is_refused(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
) -> None:
    """A second call would put a finished video back in the queue."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)

    await api_client.post(f"/api/v1/video-assets/{asset_id}/complete", headers=headers)
    second = await api_client.post(
        f"/api/v1/video-assets/{asset_id}/complete", headers=headers
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "INVALID_VIDEO_STATUS"
    assert len(queue.enqueued) == 1


async def test_a_stranger_cannot_complete_someone_elses_upload(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
) -> None:
    owner = await make_user(db_session, "instructor")
    intruder = await make_user(db_session, "instructor", email="khac2@example.com")
    lesson = await make_lesson(db_session, owner)
    asset_id = await start_upload(api_client, lesson, await sign_in(api_client, owner))

    response = await api_client.post(
        f"/api/v1/video-assets/{asset_id}/complete",
        headers=await sign_in(api_client, intruder),
    )

    assert response.status_code == 403
    assert queue.enqueued == []


# --- Trying again ----------------------------------------------------------


async def fail_the_asset(session: AsyncSession, asset_id: uuid.UUID) -> None:
    asset = await session.get(VideoAsset, asset_id)
    assert asset is not None
    asset.status = "failed"
    asset.error_message = "bucket không phản hồi"
    await session.flush()


async def test_a_failed_video_can_be_processed_again_without_re_uploading(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
) -> None:
    """Most failures are transient. The file is already in the bucket."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)
    await fail_the_asset(db_session, asset_id)

    response = await api_client.post(
        f"/api/v1/video-assets/{asset_id}/retry", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processing"
    assert body["error_message"] is None
    assert queue.enqueued == [asset_id]
    # No new signature: the same object is being processed again.
    assert len(storage.signed) == 1


async def test_only_a_failed_video_can_be_retried(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
) -> None:
    """Retrying a video that is already fine would republish it."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)

    response = await api_client.post(
        f"/api/v1/video-assets/{asset_id}/retry", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_VIDEO_STATUS"
    assert queue.enqueued == []


async def test_a_stranger_cannot_retry_someone_elses_video(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
) -> None:
    owner = await make_user(db_session, "instructor")
    intruder = await make_user(db_session, "instructor", email="khac3@example.com")
    lesson = await make_lesson(db_session, owner)
    asset_id = await start_upload(api_client, lesson, await sign_in(api_client, owner))
    await fail_the_asset(db_session, asset_id)

    response = await api_client.post(
        f"/api/v1/video-assets/{asset_id}/retry",
        headers=await sign_in(api_client, intruder),
    )

    assert response.status_code == 403
    assert queue.enqueued == []


# --- Reading the status ----------------------------------------------------


async def test_the_owner_polls_the_status(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)

    response = await api_client.get(f"/api/v1/video-assets/{asset_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "uploading"
    assert body["hls_url"] is None


async def test_a_ready_video_carries_a_playback_url(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    settings = get_settings()
    original = settings.r2_public_base_url
    object.__setattr__(settings, "r2_public_base_url", "https://cdn.example")
    try:
        owner = await make_user(db_session, "instructor")
        lesson = await make_lesson(db_session, owner)
        headers = await sign_in(api_client, owner)
        asset_id = await start_upload(api_client, lesson, headers)

        asset = await db_session.get(VideoAsset, asset_id)
        assert asset is not None
        asset.status = "ready"
        asset.hls_manifest_key = f"videos/{asset_id}/hls/index.m3u8"
        asset.duration_s = 754
        await db_session.flush()

        response = await api_client.get(
            f"/api/v1/video-assets/{asset_id}", headers=headers
        )

        body = response.json()
        assert body["status"] == "ready"
        assert body["duration_s"] == 754
        assert body["hls_url"] == f"https://cdn.example/videos/{asset_id}/hls/index.m3u8"
    finally:
        object.__setattr__(settings, "r2_public_base_url", original)


async def test_the_lesson_carries_its_video(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """So the player needs one request, not one per lesson plus one per asset."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)

    response = await api_client.get(f"/api/v1/lessons/{lesson.id}", headers=headers)

    body = response.json()
    assert body["video"]["id"] == str(asset_id)
    assert body["video"]["status"] == "uploading"


async def test_a_lesson_without_a_video_says_so(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.get(f"/api/v1/lessons/{lesson.id}", headers=headers)

    assert response.json()["video"] is None


async def test_an_orphaned_asset_is_not_found(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """No lesson means no course means no owner to compare the caller against."""
    owner = await make_user(db_session, "instructor")
    headers = await sign_in(api_client, owner)

    orphan = VideoAsset(storage_key=f"videos/{uuid.uuid4()}/original.mp4")
    db_session.add(orphan)
    await db_session.flush()

    response = await api_client.get(f"/api/v1/video-assets/{orphan.id}", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "VIDEO_ASSET_NOT_FOUND"


async def test_deleting_the_lesson_takes_its_video_with_it(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """The lesson is the only route to an asset, so a kept row is unreachable."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)

    await api_client.delete(f"/api/v1/lessons/{lesson.id}", headers=headers)

    response = await api_client.get(f"/api/v1/video-assets/{asset_id}", headers=headers)
    assert response.status_code == 404


async def test_storage_that_was_never_configured_answers_503(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deliberate: the rest of the platform runs fine without a bucket."""
    settings = get_settings()
    original = settings.r2_account_id
    object.__setattr__(settings, "r2_account_id", "")
    try:
        owner = await make_user(db_session, "instructor")
        lesson = await make_lesson(db_session, owner)
        headers = await sign_in(api_client, owner)

        response = await api_client.post(
            f"/api/v1/lessons/{lesson.id}/video", json=upload_body(), headers=headers
        )

        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "STORAGE_NOT_CONFIGURED"
    finally:
        object.__setattr__(settings, "r2_account_id", original)


async def test_the_curriculum_tree_still_hides_lesson_content(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """Adding `video` to LessonOut must not leak into the public summary."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    await start_upload(api_client, lesson, headers)

    section = await db_session.get(CourseSection, lesson.section_id)
    assert section is not None
    response = await api_client.get(
        f"/api/v1/courses/{section.course_id}/curriculum", headers=headers
    )

    summary = response.json()["sections"][0]["lessons"][0]
    assert "video" not in summary
    assert "article_content" not in summary


async def test_no_asset_row_survives_its_lesson(
    api_client: AsyncClient, db_session: AsyncSession, storage: FakeStorage
) -> None:
    """Belt and braces for the delete above, straight against the table."""
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)
    asset_id = await start_upload(api_client, lesson, headers)

    await api_client.delete(f"/api/v1/lessons/{lesson.id}", headers=headers)

    remaining = await db_session.scalars(
        select(VideoAsset).where(VideoAsset.id == asset_id)
    )
    assert list(remaining) == []
