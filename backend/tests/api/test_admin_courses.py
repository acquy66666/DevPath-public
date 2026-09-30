"""The admin's review queue: approve, reject, take down.

What must hold: only an admin decides; each decision moves exactly one status
to exactly one other; the instructor hears about every decision, with the
reason when there is one; and nothing reaches the public before approval.
The jobs that approval schedules are pinned in `test_course_ingest.py`.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Notification, User
from app.services.tasks import get_task_queue
from tests.api.fakes import FakeQueue
from tests.api.publishing import admin_headers

PASSWORD = "mật-khẩu-đủ-dài"
ADMIN = "/api/v1/admin/courses"
T0 = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


async def make_user(session: AsyncSession, role: str, name: str | None = None) -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=name or role.title(),
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
async def category(db_session: AsyncSession) -> Category:
    category = Category(name="Kiểm duyệt", slug=f"kiem-duyet-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()
    return category


@pytest.fixture
async def teacher(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor", "Cô Giảng Viên")


async def make_course(
    session: AsyncSession,
    instructor: User,
    category: Category,
    *,
    status: str = "pending_review",
    title: str = "Khóa chờ duyệt",
    updated_minutes: int = 0,
    published_at: datetime | None = None,
) -> Course:
    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title=title,
        slug=f"khoa-{uuid.uuid4().hex[:8]}",
        status=status,
        published_at=published_at or (T0 if status == "published" else None),
        rejection_reason="Lý do cũ" if status == "rejected" else None,
        updated_at=T0 + timedelta(minutes=updated_minutes),
    )
    session.add(course)
    await session.flush()
    return course


@pytest.fixture
async def admin(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await admin_headers(api_client, db_session)


@pytest.fixture
def queue(app: FastAPI) -> FakeQueue:
    fake = FakeQueue()
    app.dependency_overrides[get_task_queue] = lambda: fake
    return fake


async def notifications_of(session: AsyncSession, user: User) -> list[Notification]:
    return list(
        (await session.scalars(select(Notification).where(Notification.user_id == user.id))).all()
    )


# --- Who may ---------------------------------------------------------------


async def test_the_queue_needs_a_signed_in_admin(
    api_client: AsyncClient, db_session: AsyncSession, teacher: User
) -> None:
    assert (await api_client.get(ADMIN)).status_code == 401

    student = await make_user(db_session, "student")
    for user in (student, teacher):
        response = await api_client.get(ADMIN, headers=await sign_in(api_client, user))
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


async def test_an_instructor_cannot_reject_or_take_down(
    api_client: AsyncClient, db_session: AsyncSession, teacher: User, category: Category
) -> None:
    course = await make_course(db_session, teacher, category)
    headers = await sign_in(api_client, teacher)

    for action in ("reject", "take-down"):
        response = await api_client.post(
            f"{ADMIN}/{course.id}/{action}", json={"reason": "tự xử"}, headers=headers
        )
        assert response.status_code == 403


# --- The queue -------------------------------------------------------------


async def test_the_queue_is_pending_courses_longest_waiting_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    # A token in every title: the dev database has courses of its own.
    token = uuid.uuid4().hex[:10]
    newer = await make_course(
        db_session, teacher, category, title=f"Mới gửi {token}", updated_minutes=30
    )
    older = await make_course(db_session, teacher, category, title=f"Gửi lâu rồi {token}")
    await make_course(db_session, teacher, category, status="draft", title=f"Nháp {token}")
    await make_course(db_session, teacher, category, status="published", title=f"Bán {token}")

    response = await api_client.get(ADMIN, params={"q": token}, headers=admin)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(older.id), str(newer.id)]
    assert body["total"] == 2
    first = body["items"][0]
    assert first["instructor"]["email"] == teacher.email
    assert first["category"]["id"] == str(category.id)
    assert first["lessons_count"] == 0


async def test_the_queue_filters_by_status_and_searches_the_instructor(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    other = await make_user(db_session, "instructor", "Thầy Khác")
    mine = await make_course(db_session, teacher, category, status="published")
    await make_course(db_session, other, category, status="published")

    response = await api_client.get(
        ADMIN, params={"status": "published", "q": teacher.email}, headers=admin
    )

    assert [item["id"] for item in response.json()["items"]] == [str(mine.id)]


async def test_one_course_in_any_status_and_an_unknown_one(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    draft = await make_course(db_session, teacher, category, status="draft")

    found = await api_client.get(f"{ADMIN}/{draft.id}", headers=admin)
    missing = await api_client.get(f"{ADMIN}/{uuid.uuid4()}", headers=admin)

    assert found.status_code == 200
    assert found.json()["status"] == "draft"
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_an_admin_reads_a_pending_course_and_its_lessons(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    """Reviewing means reading: the ordinary course endpoints already open a
    course in any status to an admin."""
    course = await make_course(db_session, teacher, category)

    detail = await api_client.get(f"/api/v1/courses/{course.id}", headers=admin)
    curriculum = await api_client.get(f"/api/v1/courses/{course.id}/curriculum", headers=admin)

    assert detail.status_code == 200
    assert curriculum.status_code == 200


# --- Approve ---------------------------------------------------------------


async def test_approving_publishes_and_tells_the_instructor(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    queue: FakeQueue,
    teacher: User,
    category: Category,
) -> None:
    course = await make_course(db_session, teacher, category)
    assert (await api_client.get(f"/api/v1/courses/{course.id}")).status_code == 404

    response = await api_client.post(f"{ADMIN}/{course.id}/approve", headers=admin)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None
    assert body["rejection_reason"] is None
    assert (await api_client.get(f"/api/v1/courses/{course.id}")).status_code == 200

    [notification] = await notifications_of(db_session, teacher)
    assert notification.type == "course_approved"
    assert notification.payload == {
        "course_id": str(course.id),
        "course_slug": course.slug,
        "course_title": course.title,
    }


async def test_approving_again_keeps_the_first_publication_date(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    queue: FakeQueue,
    teacher: User,
    category: Category,
) -> None:
    """A course taken down and approved again first went on sale back then."""
    course = await make_course(db_session, teacher, category, published_at=T0)

    response = await api_client.post(f"{ADMIN}/{course.id}/approve", headers=admin)

    assert datetime.fromisoformat(response.json()["published_at"]) == T0


@pytest.mark.parametrize("status", ["draft", "published", "rejected"])
async def test_only_a_pending_course_can_be_approved(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    queue: FakeQueue,
    teacher: User,
    category: Category,
    status: str,
) -> None:
    course = await make_course(db_session, teacher, category, status=status)

    response = await api_client.post(f"{ADMIN}/{course.id}/approve", headers=admin)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_COURSE_STATUS"
    assert queue.ingested == []


async def test_a_deleted_course_is_not_there_to_approve(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    queue: FakeQueue,
    teacher: User,
    category: Category,
) -> None:
    course = await make_course(db_session, teacher, category)
    course.deleted_at = datetime.now(tz=UTC)
    await db_session.flush()

    response = await api_client.post(f"{ADMIN}/{course.id}/approve", headers=admin)

    assert response.status_code == 404


# --- Reject ----------------------------------------------------------------


async def test_rejecting_sends_the_course_back_with_the_reason(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    course = await make_course(db_session, teacher, category)

    response = await api_client.post(
        f"{ADMIN}/{course.id}/reject",
        json={"reason": "  Video bài 3 không có tiếng  "},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert response.json()["rejection_reason"] == "Video bài 3 không có tiếng"

    # The instructor reads it on their own course, and in the bell.
    own = await api_client.get(
        f"/api/v1/courses/{course.id}", headers=await sign_in(api_client, teacher)
    )
    assert own.json()["rejection_reason"] == "Video bài 3 không có tiếng"
    [notification] = await notifications_of(db_session, teacher)
    assert notification.type == "course_rejected"
    assert notification.payload["reason"] == "Video bài 3 không có tiếng"


async def test_a_rejection_needs_a_reason(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    course = await make_course(db_session, teacher, category)

    for body in ({}, {"reason": "   "}):
        response = await api_client.post(f"{ADMIN}/{course.id}/reject", json=body, headers=admin)
        assert response.status_code == 422

    await db_session.refresh(course)
    assert course.status == "pending_review"


async def test_sending_a_rejected_course_again_clears_the_old_reason(
    api_client: AsyncClient, db_session: AsyncSession, teacher: User, category: Category
) -> None:
    course = await make_course(db_session, teacher, category, status="rejected")

    response = await api_client.post(
        f"/api/v1/courses/{course.id}/submit", headers=await sign_in(api_client, teacher)
    )

    assert response.json()["status"] == "pending_review"
    assert response.json()["rejection_reason"] is None


async def test_only_a_pending_course_can_be_rejected(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    course = await make_course(db_session, teacher, category, status="published")

    response = await api_client.post(
        f"{ADMIN}/{course.id}/reject", json={"reason": "muộn rồi"}, headers=admin
    )

    assert response.status_code == 409


# --- Take down -------------------------------------------------------------


async def test_taking_down_returns_a_published_course_to_draft(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    course = await make_course(db_session, teacher, category, status="published")

    response = await api_client.post(
        f"{ADMIN}/{course.id}/take-down", json={"reason": "Vi phạm bản quyền"}, headers=admin
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft"
    assert (await api_client.get(f"/api/v1/courses/{course.id}")).status_code == 404
    [notification] = await notifications_of(db_session, teacher)
    assert notification.type == "course_taken_down"
    assert notification.payload["reason"] == "Vi phạm bản quyền"


async def test_only_a_published_course_can_be_taken_down(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    course = await make_course(db_session, teacher, category)

    response = await api_client.post(
        f"{ADMIN}/{course.id}/take-down", json={"reason": "?"}, headers=admin
    )

    assert response.status_code == 409


# --- The tab badges --------------------------------------------------------


async def test_the_summary_counts_what_waits(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict[str, str],
    teacher: User,
    category: Category,
) -> None:
    before = (await api_client.get("/api/v1/admin/summary", headers=admin)).json()
    await make_course(db_session, teacher, category)
    await make_course(db_session, teacher, category, status="draft")
    student = await make_user(db_session, "student")
    student.locked_at = datetime.now(tz=UTC)
    await db_session.flush()

    after = (await api_client.get("/api/v1/admin/summary", headers=admin)).json()

    assert after["pending_courses"] == before["pending_courses"] + 1
    assert after["locked_users"] == before["locked_users"] + 1
    assert after["pending_reports"] == before["pending_reports"]
