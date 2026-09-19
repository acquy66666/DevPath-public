"""Uploading and removing a video's transcript.

The file is read before it is kept -- that is the reason it comes through the
API at all -- so most of what is tested here is what gets refused, and that a
refusal leaves nothing behind in either the bucket or the row.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, CourseSection, Lesson, User, VideoAsset
from app.services.storage import get_storage
from app.services.tasks import get_task_queue
from tests.api.fakes import FakeQueue, FakeStorage, UnwritableStorage
from tests.api.test_video_upload import make_lesson, make_user, sign_in

SRT = (
    "1\n00:00:01,000 --> 00:00:03,000\nBiến là một cái tên\n\n"
    "2\n00:00:03,000 --> 00:00:05,000\ngắn với một giá trị.\n"
)


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


async def with_video(session: AsyncSession, lesson: Lesson) -> VideoAsset:
    asset_id = uuid.uuid4()
    asset = VideoAsset(
        id=asset_id, storage_key=f"videos/{asset_id}/original.mp4", status="ready"
    )
    session.add(asset)
    lesson.video_asset = asset
    await session.flush()
    # Attaching it was an UPDATE on `lessons`, whose `updated_at` Postgres
    # fills in -- expired until read back, and the API shares this session.
    await session.refresh(lesson)
    return asset


async def course_of(session: AsyncSession, lesson: Lesson) -> Course:
    section = await session.get(CourseSection, lesson.section_id)
    return await session.get(Course, section.course_id)


async def publish(session: AsyncSession, lesson: Lesson) -> Course:
    course = await course_of(session, lesson)
    course.status = "published"
    course.published_at = datetime.now(tz=UTC)
    await session.flush()
    return course


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def lesson(db_session: AsyncSession, owner: User) -> Lesson:
    lesson = await make_lesson(db_session, owner)
    await with_video(db_session, lesson)
    return lesson


def body(filename: str = "bai-1.srt", content: str = SRT) -> dict:
    return {"filename": filename, "content": content}


# --- Uploading -----------------------------------------------------------------


async def test_a_transcript_is_read_then_kept_beside_its_video(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript", json=body(), headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "format": "srt",
        "characters": len("Biến là một cái tên gắn với một giá trị."),
        # A draft is ingested when it is published, not on every upload.
        "ingest_queued": False,
    }

    asset = lesson.video_asset
    await db_session.refresh(asset)
    key = f"videos/{asset.id}/transcript.srt"
    assert asset.transcript_key == key
    # The original, timings and all -- not the extracted text.
    assert storage.objects[key] == (SRT.encode("utf-8"), "application/x-subrip; charset=utf-8")
    assert queue.ingested == []


async def test_on_a_published_course_the_upload_queues_an_ingest(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    course = await publish(db_session, lesson)
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript", json=body(), headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["ingest_queued"] is True
    assert queue.ingested == [course.id]


async def test_uploading_again_in_the_other_format_replaces_the_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    """`.srt` and `.txt` live under different keys; the old one must not stay
    behind in the bucket after the row stops pointing at it."""
    headers = await sign_in(api_client, owner)
    url = f"/api/v1/lessons/{lesson.id}/transcript"
    await api_client.put(url, json=body(), headers=headers)

    response = await api_client.put(
        url, json=body("bai-1.txt", "Một đoạn văn bản thường."), headers=headers
    )

    assert response.status_code == 200, response.text
    asset = lesson.video_asset
    await db_session.refresh(asset)
    assert asset.transcript_key == f"videos/{asset.id}/transcript.txt"
    assert f"videos/{asset.id}/transcript.srt" not in storage.objects
    assert f"videos/{asset.id}/transcript.txt" in storage.objects


async def test_the_lesson_says_which_transcript_it_has(
    api_client: AsyncClient,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    headers = await sign_in(api_client, owner)
    before = await api_client.get(f"/api/v1/lessons/{lesson.id}", headers=headers)
    await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript", json=body(), headers=headers
    )
    after = await api_client.get(f"/api/v1/lessons/{lesson.id}", headers=headers)

    assert before.json()["video"]["transcript_format"] is None
    assert after.json()["video"]["transcript_format"] == "srt"


# --- Refusals ------------------------------------------------------------------


async def test_a_file_that_was_not_utf8_is_refused_and_nothing_is_kept(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    headers = await sign_in(api_client, owner)
    broken = SRT.replace("ế", "\ufffd").replace("ị", "\ufffd")

    response = await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript",
        json=body(content=broken),
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "TRANSCRIPT_UNREADABLE"
    assert storage.objects == {}
    await db_session.refresh(lesson.video_asset)
    assert lesson.video_asset.transcript_key is None


async def test_an_srt_with_no_timings_is_refused(
    api_client: AsyncClient,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript",
        json=body(content="Văn bản thường, đặt nhầm đuôi .srt"),
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "TRANSCRIPT_UNREADABLE"


@pytest.mark.parametrize("filename", ["phu-de.vtt", "bai-1.docx", "srt"])
async def test_only_srt_and_txt_are_accepted(
    api_client: AsyncClient,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
    filename: str,
) -> None:
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript",
        json=body(filename=filename),
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


async def test_a_bucket_that_refuses_leaves_the_lesson_as_it_was(
    app: FastAPI,
    api_client: AsyncClient,
    db_session: AsyncSession,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    app.dependency_overrides[get_storage] = UnwritableStorage
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript", json=body(), headers=headers
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "STORAGE_ERROR"
    await db_session.refresh(lesson.video_asset)
    assert lesson.video_asset.transcript_key is None


async def test_an_article_has_no_transcript(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
) -> None:
    article = await make_lesson(db_session, owner, lesson_type="article")
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{article.id}/transcript", json=body(), headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "LESSON_NOT_VIDEO"


async def test_a_video_lesson_needs_its_video_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
) -> None:
    empty = await make_lesson(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{empty.id}/transcript", json=body(), headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "LESSON_HAS_NO_VIDEO"


async def test_signing_in_is_required(
    api_client: AsyncClient, storage: FakeStorage, queue: FakeQueue, lesson: Lesson
) -> None:
    response = await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript", json=body()
    )

    assert response.status_code == 401


async def test_another_instructor_cannot_touch_it(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    lesson: Lesson,
) -> None:
    stranger = await make_user(db_session, "instructor")
    headers = await sign_in(api_client, stranger)
    url = f"/api/v1/lessons/{lesson.id}/transcript"

    put = await api_client.put(url, json=body(), headers=headers)
    delete = await api_client.delete(url, headers=headers)

    assert put.status_code == 403
    assert delete.status_code == 403
    assert storage.objects == {}


async def test_an_unknown_lesson_is_404(
    api_client: AsyncClient, storage: FakeStorage, queue: FakeQueue, owner: User
) -> None:
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        f"/api/v1/lessons/{uuid.uuid4()}/transcript", json=body(), headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LESSON_NOT_FOUND"


# --- Removing ------------------------------------------------------------------


async def test_removing_a_transcript_clears_the_row_the_bucket_and_the_index(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    """On a live course the chunks are the part a student would notice: the
    re-ingest queued here is what takes them out of the chatbot's reach."""
    course = await publish(db_session, lesson)
    headers = await sign_in(api_client, owner)
    url = f"/api/v1/lessons/{lesson.id}/transcript"
    await api_client.put(url, json=body(), headers=headers)
    queue.ingested.clear()

    response = await api_client.delete(url, headers=headers)

    assert response.status_code == 204
    await db_session.refresh(lesson.video_asset)
    assert lesson.video_asset.transcript_key is None
    assert storage.objects == {}
    assert queue.ingested == [course.id]


async def test_removing_what_is_not_there_is_404(
    api_client: AsyncClient,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    headers = await sign_in(api_client, owner)

    response = await api_client.delete(
        f"/api/v1/lessons/{lesson.id}/transcript", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "TRANSCRIPT_NOT_FOUND"


# --- Replacing the video -------------------------------------------------------


async def test_replacing_the_video_of_a_live_course_re_ingests_its_transcript_away(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    """The transcript went with the old asset. Without a re-ingest its chunks
    would keep answering questions about a recording nobody can watch."""
    course = await publish(db_session, lesson)
    headers = await sign_in(api_client, owner)
    await api_client.put(
        f"/api/v1/lessons/{lesson.id}/transcript", json=body(), headers=headers
    )
    queue.ingested.clear()

    response = await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video",
        json={"filename": "moi.mp4", "content_type": "video/mp4", "size_bytes": 1024},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert queue.ingested == [course.id]


async def test_replacing_a_video_with_no_transcript_queues_nothing(
    api_client: AsyncClient,
    db_session: AsyncSession,
    storage: FakeStorage,
    queue: FakeQueue,
    owner: User,
    lesson: Lesson,
) -> None:
    await publish(db_session, lesson)
    headers = await sign_in(api_client, owner)

    await api_client.post(
        f"/api/v1/lessons/{lesson.id}/video",
        json={"filename": "moi.mp4", "content_type": "video/mp4", "size_bytes": 1024},
        headers=headers,
    )

    assert queue.ingested == []
