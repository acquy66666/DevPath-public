"""Watching a course: what unlocks, what gets remembered, and when it is done.

Two rules run through all of it. Progress belongs to an enrolment, so nobody
without one can write any; and finishing a course is not something anyone
declares, it is what "every lesson is finished" adds up to.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    Category,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonProgress,
    User,
)

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
    session: AsyncSession, owner: User, *, lessons: int = 2
) -> tuple[Course, list[Lesson]]:
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title="Khóa học có video",
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    rows = [
        Lesson(
            section_id=section.id,
            title=f"Bài {index + 1}",
            type="video",
            position=index,
            # The first lesson is the free sample; the rest need an enrolment.
            is_preview=index == 0,
        )
        for index in range(lessons)
    ]
    session.add_all(rows)
    await session.flush()
    return course, rows


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


async def enrol(client: AsyncClient, course: Course, headers: dict[str, str]) -> None:
    response = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert response.status_code in (200, 201)


def progress_url(lesson: Lesson) -> str:
    return f"/api/v1/lessons/{lesson.id}/progress"


# --- What enrolling unlocks ------------------------------------------------


async def test_an_enrolled_student_can_open_a_locked_lesson(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    locked = lessons[1]

    before = await api_client.get(f"/api/v1/lessons/{locked.id}", headers=headers)
    await enrol(api_client, course, headers)
    after = await api_client.get(f"/api/v1/lessons/{locked.id}", headers=headers)

    assert before.status_code == 403
    assert after.status_code == 200
    assert after.json()["title"] == locked.title


async def test_someone_who_never_enrolled_still_sees_only_the_preview(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    preview = await api_client.get(f"/api/v1/lessons/{lessons[0].id}", headers=headers)
    locked = await api_client.get(f"/api/v1/lessons/{lessons[1].id}", headers=headers)

    assert preview.status_code == 200
    assert locked.status_code == 403
    assert locked.json()["detail"]["code"] == "LESSON_LOCKED"


# --- The heartbeat ---------------------------------------------------------


async def test_the_first_heartbeat_writes_the_position(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    response = await api_client.put(
        progress_url(lessons[0]), json={"last_position_s": 42}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["lesson_id"] == str(lessons[0].id)
    assert body["last_position_s"] == 42
    assert body["completed_at"] is None


async def test_heartbeats_move_one_row_rather_than_writing_many(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """Ten seconds apart for an hour is 360 writes. They are all the same row."""
    course, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    for position in (10, 20, 30):
        await api_client.put(
            progress_url(lessons[0]),
            json={"last_position_s": position},
            headers=headers,
        )

    rows = list(
        await db_session.scalars(
            select(LessonProgress).where(LessonProgress.lesson_id == lessons[0].id)
        )
    )
    assert len(rows) == 1
    assert rows[0].last_position_s == 30


async def test_a_heartbeat_cannot_un_finish_a_lesson(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """This is why `completed` is optional instead of defaulting to False."""
    course, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 100, "completed": True},
        headers=headers,
    )
    after = await api_client.put(
        progress_url(lessons[0]), json={"last_position_s": 110}, headers=headers
    )

    assert after.json()["completed_at"] is not None
    assert after.json()["last_position_s"] == 110


async def test_finishing_twice_keeps_the_first_time(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    first = await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 100, "completed": True},
        headers=headers,
    )
    second = await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 120, "completed": True},
        headers=headers,
    )

    assert first.json()["completed_at"] == second.json()["completed_at"]


async def test_a_lesson_can_be_un_finished_on_purpose(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 100, "completed": True},
        headers=headers,
    )
    response = await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 100, "completed": False},
        headers=headers,
    )

    assert response.json()["completed_at"] is None


async def test_progress_without_an_enrolment_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """Even on the preview lesson: there is no enrolment to hang it on."""
    _, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.put(
        progress_url(lessons[0]), json={"last_position_s": 5}, headers=headers
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_ENROLLED"


async def test_the_instructor_has_no_progress_to_record(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """They cannot enrol in their own course, so they cannot study it either."""
    _, lessons = await make_course(db_session, owner)
    headers = await sign_in(api_client, owner)

    response = await api_client.put(
        progress_url(lessons[0]), json={"last_position_s": 5}, headers=headers
    )

    assert response.status_code == 403


async def test_saving_progress_requires_signing_in(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    _, lessons = await make_course(db_session, owner)

    response = await api_client.put(progress_url(lessons[0]), json={"last_position_s": 5})

    assert response.status_code == 401


@pytest.mark.parametrize("position", [-1, 24 * 60 * 60 + 1])
async def test_an_impossible_position_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, student: User, position: int
) -> None:
    headers = await sign_in(api_client, student)

    response = await api_client.put(
        f"/api/v1/lessons/{uuid.uuid4()}/progress",
        json={"last_position_s": position},
        headers=headers,
    )

    assert response.status_code == 422


async def test_an_unknown_lesson_is_404(
    api_client: AsyncClient, db_session: AsyncSession, student: User
) -> None:
    headers = await sign_in(api_client, student)

    response = await api_client.put(
        f"/api/v1/lessons/{uuid.uuid4()}/progress",
        json={"last_position_s": 5},
        headers=headers,
    )

    assert response.status_code == 404


# --- Finishing the course --------------------------------------------------


async def test_finishing_every_lesson_finishes_the_course(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner, lessons=2)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 10, "completed": True},
        headers=headers,
    )
    halfway = await api_client.get(
        f"/api/v1/courses/{course.id}/progress", headers=headers
    )
    assert halfway.json()["completed_at"] is None

    await api_client.put(
        progress_url(lessons[1]),
        json={"last_position_s": 10, "completed": True},
        headers=headers,
    )
    finished = await api_client.get(
        f"/api/v1/courses/{course.id}/progress", headers=headers
    )

    assert finished.json()["completed_at"] is not None
    assert finished.json()["completed_count"] == 2


async def test_un_finishing_one_lesson_reopens_the_course(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner, lessons=2)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    for lesson in lessons:
        await api_client.put(
            progress_url(lesson),
            json={"last_position_s": 10, "completed": True},
            headers=headers,
        )
    await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 10, "completed": False},
        headers=headers,
    )

    body = (
        await api_client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    ).json()

    assert body["completed_at"] is None
    assert body["completed_count"] == 1


async def test_an_empty_course_is_not_a_finished_course(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _ = await make_course(db_session, owner, lessons=0)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    body = (
        await api_client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    ).json()

    assert body["lesson_count"] == 0
    assert body["completed_at"] is None
    assert body["resume_lesson_id"] is None


# --- Reading a course's progress -------------------------------------------


async def test_the_course_progress_counts_and_lists(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner, lessons=3)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 90, "completed": True},
        headers=headers,
    )
    await api_client.put(
        progress_url(lessons[1]), json={"last_position_s": 30}, headers=headers
    )

    body = (
        await api_client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    ).json()

    assert body["lesson_count"] == 3
    assert body["completed_count"] == 1
    positions = {row["lesson_id"]: row["last_position_s"] for row in body["lessons"]}
    assert positions[str(lessons[0].id)] == 90
    assert positions[str(lessons[1].id)] == 30
    # A lesson nobody has opened has no row at all, rather than a row of zeroes.
    assert str(lessons[2].id) not in positions


async def test_resume_points_at_the_lesson_touched_last(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner, lessons=2)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    await api_client.put(
        progress_url(lessons[0]), json={"last_position_s": 10}, headers=headers
    )
    await api_client.put(
        progress_url(lessons[1]), json={"last_position_s": 20}, headers=headers
    )

    # Both rows carry the same `updated_at`: this whole test is one
    # transaction, and `now()` is its start time. Backdating the first is what
    # makes "touched last" mean anything here.
    await db_session.execute(
        update(LessonProgress)
        .where(LessonProgress.lesson_id == lessons[0].id)
        .values(updated_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await db_session.flush()

    body = (
        await api_client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    ).json()

    assert body["resume_lesson_id"] == str(lessons[1].id)


async def test_resume_starts_at_the_beginning_when_nothing_was_watched(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner, lessons=2)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    body = (
        await api_client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    ).json()

    assert body["resume_lesson_id"] == str(lessons[0].id)
    assert body["lessons"] == []


async def test_one_students_progress_is_not_anothers(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, lessons = await make_course(db_session, owner, lessons=2)
    mine = await sign_in(api_client, student)
    await enrol(api_client, course, mine)
    await api_client.put(
        progress_url(lessons[0]),
        json={"last_position_s": 55, "completed": True},
        headers=mine,
    )

    other = await make_user(db_session, "student")
    theirs = await sign_in(api_client, other)
    await enrol(api_client, course, theirs)

    body = (
        await api_client.get(f"/api/v1/courses/{course.id}/progress", headers=theirs)
    ).json()

    assert body["lessons"] == []
    assert body["completed_count"] == 0
    assert body["enrollment_id"] != str(
        (
            await db_session.scalar(
                select(Enrollment).where(Enrollment.user_id == student.id)
            )
        ).id
    )


async def test_reading_progress_needs_an_enrolment(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.get(
        f"/api/v1/courses/{course.id}/progress", headers=headers
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_ENROLLED"
