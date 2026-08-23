"""Notes and bookmarks.

The rule worth checking most: writing on a lesson needs exactly the permission
that reading it needs -- no more, and no less. The preview lesson is where the
two could have drifted apart, so it appears in both halves of this file.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Bookmark, Category, Course, CourseSection, Lesson, Note, User

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
    session: AsyncSession, owner: User
) -> tuple[Course, Lesson, Lesson]:
    """A published course whose first lesson is free and second is not."""
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title="Khóa học có ghi chú",
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

    preview = Lesson(
        section_id=section.id, title="Bài học thử", type="video", position=0, is_preview=True
    )
    locked = Lesson(
        section_id=section.id, title="Bài trả phí", type="video", position=1
    )
    session.add_all([preview, locked])
    await session.flush()
    return course, preview, locked


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


async def enrol(client: AsyncClient, course: Course, headers: dict[str, str]) -> None:
    response = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert response.status_code in (200, 201)


def notes_url(lesson: Lesson) -> str:
    return f"/api/v1/lessons/{lesson.id}/notes"


def bookmark_url(lesson: Lesson) -> str:
    return f"/api/v1/lessons/{lesson.id}/bookmark"


# --- Notes -----------------------------------------------------------------


async def test_a_note_records_the_moment_it_is_about(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _, locked = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    response = await api_client.post(
        notes_url(locked),
        json={"content": "Chỗ này giải thích vòng lặp rất rõ", "timestamp_s": 245},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["timestamp_s"] == 245
    assert body["content"] == "Chỗ này giải thích vòng lặp rất rõ"
    assert body["lesson_id"] == str(locked.id)


async def test_the_free_sample_can_be_annotated_without_enrolling(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """Writing needs the permission reading needs, and no more."""
    _, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.post(
        notes_url(preview), json={"content": "Ghi trên bài học thử"}, headers=headers
    )

    assert response.status_code == 201
    # No timestamp given: zero means "this lesson", not "the first second".
    assert response.json()["timestamp_s"] == 0


async def test_a_locked_lesson_cannot_be_annotated(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """...and no less."""
    _, _, locked = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.post(
        notes_url(locked), json={"content": "Không được phép"}, headers=headers
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LESSON_LOCKED"


async def test_notes_come_back_in_the_order_of_the_video(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    for seconds, text in ((300, "Cuối"), (10, "Đầu"), (120, "Giữa")):
        await api_client.post(
            notes_url(preview),
            json={"content": text, "timestamp_s": seconds},
            headers=headers,
        )

    body = (await api_client.get(notes_url(preview), headers=headers)).json()

    assert [note["content"] for note in body] == ["Đầu", "Giữa", "Cuối"]


async def test_one_persons_notes_are_not_anothers(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    _, preview, _ = await make_course(db_session, owner)
    mine = await sign_in(api_client, student)
    await api_client.post(
        notes_url(preview), json={"content": "Của tôi"}, headers=mine
    )

    stranger = await make_user(db_session, "student")
    theirs = await sign_in(api_client, stranger)

    assert (await api_client.get(notes_url(preview), headers=theirs)).json() == []


async def test_a_note_can_be_edited(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    _, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    created = (
        await api_client.post(
            notes_url(preview),
            json={"content": "Bản nháp", "timestamp_s": 30},
            headers=headers,
        )
    ).json()

    response = await api_client.patch(
        f"/api/v1/notes/{created['id']}",
        json={"content": "Bản sửa", "timestamp_s": 45},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Bản sửa"
    assert response.json()["timestamp_s"] == 45


async def test_somebody_elses_note_is_not_found_rather_than_forbidden(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """403 would confirm the note exists. There is nothing to gain from that."""
    _, preview, _ = await make_course(db_session, owner)
    created = (
        await api_client.post(
            notes_url(preview),
            json={"content": "Của tôi"},
            headers=await sign_in(api_client, student),
        )
    ).json()

    stranger = await make_user(db_session, "student")
    theirs = await sign_in(api_client, stranger)

    edit = await api_client.patch(
        f"/api/v1/notes/{created['id']}", json={"content": "Sửa trộm"}, headers=theirs
    )
    remove = await api_client.delete(f"/api/v1/notes/{created['id']}", headers=theirs)

    assert edit.status_code == remove.status_code == 404
    assert edit.json()["detail"]["code"] == "NOTE_NOT_FOUND"


async def test_a_note_can_be_deleted(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    _, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    created = (
        await api_client.post(
            notes_url(preview), json={"content": "Xóa tôi đi"}, headers=headers
        )
    ).json()

    response = await api_client.delete(f"/api/v1/notes/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert (await api_client.get(notes_url(preview), headers=headers)).json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"content": ""},
        {"content": "   "},
        {"content": "x" * 2001},
        {"content": "hợp lệ", "timestamp_s": -1},
        {"content": "hợp lệ", "timestamp_s": 24 * 60 * 60 + 1},
    ],
)
async def test_a_note_that_says_nothing_is_refused(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User, payload: dict
) -> None:
    _, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.post(notes_url(preview), json=payload, headers=headers)

    assert response.status_code == 422


async def test_notes_require_signing_in(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    _, preview, _ = await make_course(db_session, owner)

    listing = await api_client.get(notes_url(preview))
    writing = await api_client.post(notes_url(preview), json={"content": "Xin chào"})

    assert listing.status_code == writing.status_code == 401


# --- Bookmarks -------------------------------------------------------------


async def test_a_bookmark_shows_up_in_the_courses_list(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, preview, locked = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    response = await api_client.put(bookmark_url(locked), headers=headers)
    listing = await api_client.get(
        f"/api/v1/courses/{course.id}/bookmarks", headers=headers
    )

    assert response.status_code == 204
    assert listing.json()["lesson_ids"] == [str(locked.id)]
    assert str(preview.id) not in listing.json()["lesson_ids"]


async def test_bookmarking_twice_leaves_one_bookmark(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    _, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    await api_client.put(bookmark_url(preview), headers=headers)
    second = await api_client.put(bookmark_url(preview), headers=headers)

    assert second.status_code == 204
    count = await db_session.scalar(
        select(func.count()).select_from(Bookmark).where(Bookmark.lesson_id == preview.id)
    )
    assert count == 1


async def test_a_bookmark_can_be_removed_and_removing_it_again_is_fine(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.put(bookmark_url(preview), headers=headers)

    first = await api_client.delete(bookmark_url(preview), headers=headers)
    again = await api_client.delete(bookmark_url(preview), headers=headers)
    listing = await api_client.get(
        f"/api/v1/courses/{course.id}/bookmarks", headers=headers
    )

    assert first.status_code == again.status_code == 204
    assert listing.json()["lesson_ids"] == []


async def test_a_locked_lesson_cannot_be_bookmarked(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    _, _, locked = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    response = await api_client.put(bookmark_url(locked), headers=headers)

    assert response.status_code == 403


async def test_one_persons_bookmarks_are_not_anothers(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, preview, _ = await make_course(db_session, owner)
    await api_client.put(
        bookmark_url(preview), headers=await sign_in(api_client, student)
    )

    stranger = await make_user(db_session, "student")
    listing = await api_client.get(
        f"/api/v1/courses/{course.id}/bookmarks",
        headers=await sign_in(api_client, stranger),
    )

    assert listing.json()["lesson_ids"] == []


async def test_the_list_covers_only_this_course(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    first_course, first_lesson, _ = await make_course(db_session, owner)
    _, other_lesson, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)

    await api_client.put(bookmark_url(first_lesson), headers=headers)
    await api_client.put(bookmark_url(other_lesson), headers=headers)

    listing = await api_client.get(
        f"/api/v1/courses/{first_course.id}/bookmarks", headers=headers
    )

    assert listing.json()["lesson_ids"] == [str(first_lesson.id)]


async def test_bookmarks_require_signing_in(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course, preview, _ = await make_course(db_session, owner)

    setting = await api_client.put(bookmark_url(preview))
    listing = await api_client.get(f"/api/v1/courses/{course.id}/bookmarks")

    assert setting.status_code == listing.status_code == 401


async def test_deleting_a_lesson_takes_its_notes_and_bookmarks_with_it(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """ON DELETE CASCADE on both, so an instructor tidying up leaves nothing behind."""
    _, preview, _ = await make_course(db_session, owner)
    headers = await sign_in(api_client, student)
    await api_client.post(notes_url(preview), json={"content": "Ghi chú"}, headers=headers)
    await api_client.put(bookmark_url(preview), headers=headers)

    await api_client.delete(
        f"/api/v1/lessons/{preview.id}", headers=await sign_in(api_client, owner)
    )

    notes = await db_session.scalar(
        select(func.count()).select_from(Note).where(Note.lesson_id == preview.id)
    )
    bookmarks = await db_session.scalar(
        select(func.count()).select_from(Bookmark).where(Bookmark.lesson_id == preview.id)
    )
    assert notes == 0
    assert bookmarks == 0
