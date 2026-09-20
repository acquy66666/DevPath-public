"""Publishing a course is what schedules its ingest.

One seam, and it is the kind that breaks silently: nothing on the page changes
when the job is not queued, the chatbot simply answers "tôi không tìm thấy
thông tin này trong khóa học" forever, and the first person to notice is an
examiner at the demo.
"""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Category, Course, User
from app.services.tasks import get_task_queue
from tests.api.fakes import FakeQueue

PASSWORD = "mật-khẩu-đủ-dài"


@pytest.fixture
def queue(app: FastAPI) -> FakeQueue:
    fake = FakeQueue()
    app.dependency_overrides[get_task_queue] = lambda: fake
    return fake


async def make_instructor(session: AsyncSession) -> User:
    user = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash=hash_password(PASSWORD),
        role="instructor",
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
async def draft(db_session: AsyncSession) -> tuple[User, Course]:
    instructor = await make_instructor(db_session)
    category = Category(name="Lập trình", slug=f"lt-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title="Khóa nháp",
        slug=f"khoa-nhap-{uuid.uuid4().hex[:8]}",
        status="draft",
    )
    db_session.add(course)
    await db_session.flush()
    return instructor, course


async def test_publishing_a_course_schedules_its_ingest(
    api_client: AsyncClient, queue: FakeQueue, draft: tuple[User, Course]
) -> None:
    instructor, course = draft

    response = await api_client.post(
        f"/api/v1/courses/{course.id}/submit",
        headers=await sign_in(api_client, instructor),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
    assert queue.ingested == [course.id]


async def test_a_course_that_only_reaches_review_is_not_ingested(
    api_client: AsyncClient,
    queue: FakeQueue,
    draft: tuple[User, Course],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the auto-approve flag off -- which is what Phase 5's admin queue
    turns it into -- the course stops at `pending_review`. Embedding it then
    would let the chatbot quote a course no student can open."""
    instructor, course = draft
    settings = get_settings()
    monkeypatch.setattr(settings, "auto_approve_courses", False, raising=False)

    response = await api_client.post(
        f"/api/v1/courses/{course.id}/submit",
        headers=await sign_in(api_client, instructor),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending_review"
    assert queue.ingested == []
    assert queue.embedded == []


async def test_a_refused_publish_schedules_nothing(
    api_client: AsyncClient, queue: FakeQueue, draft: tuple[User, Course]
) -> None:
    """Submitting an already-published course is a 409. The job must not be
    queued anyway -- an ingest is dozens of paid API calls."""
    instructor, course = draft
    headers = await sign_in(api_client, instructor)
    await api_client.post(f"/api/v1/courses/{course.id}/submit", headers=headers)
    queue.ingested.clear()

    again = await api_client.post(
        f"/api/v1/courses/{course.id}/submit", headers=headers
    )

    assert again.status_code == 409
    assert queue.ingested == []


async def test_somebody_else_s_course_is_neither_published_nor_ingested(
    api_client: AsyncClient,
    queue: FakeQueue,
    db_session: AsyncSession,
    draft: tuple[User, Course],
) -> None:
    _, course = draft
    stranger = await make_instructor(db_session)

    response = await api_client.post(
        f"/api/v1/courses/{course.id}/submit",
        headers=await sign_in(api_client, stranger),
    )

    assert response.status_code == 403
    assert queue.ingested == []


async def test_publishing_a_course_schedules_its_embedding(
    api_client: AsyncClient, queue: FakeQueue, draft: tuple[User, Course]
) -> None:
    """The other job publishing starts, and the other thing that breaks in
    silence: with no vector the course simply never appears under "Khóa học
    tương tự", on its own page or on anybody else's."""
    instructor, course = draft

    response = await api_client.post(
        f"/api/v1/courses/{course.id}/submit",
        headers=await sign_in(api_client, instructor),
    )

    assert response.status_code == 200, response.text
    assert queue.embedded == [course.id]
