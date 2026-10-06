"""Q&A under a lesson.

The rules worth pinning, in the order a thread lives through them: who may ask
(the course's learners and staff -- not a visitor on the free preview lesson),
how the board is ordered, what a vote is, which reply wears the instructor's
badge, who is told about an answer, and who may change or remove what.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    Category,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Notification,
    QaReply,
    QaThread,
    QaVote,
    User,
)

PASSWORD = "mật-khẩu-đủ-dài"


async def make_user(session: AsyncSession, role: str = "student", name: str | None = None) -> User:
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
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_course(
    session: AsyncSession, owner: User, *, status: str = "published"
) -> tuple[Course, Lesson, Lesson]:
    """A course whose first lesson is a free preview and second is not."""
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title="Khóa học có hỏi đáp",
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status=status,
        published_at=datetime.now(UTC) if status == "published" else None,
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    preview = Lesson(
        section_id=section.id, title="Bài học thử", type="video", position=0, is_preview=True
    )
    locked = Lesson(section_id=section.id, title="Vòng lặp for", type="video", position=1)
    session.add_all([preview, locked])
    await session.flush()
    return course, preview, locked


async def enrol(session: AsyncSession, course: Course, user: User) -> None:
    session.add(Enrollment(user_id=user.id, course_id=course.id, source="free"))
    await session.flush()


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor", "Cô Giảng Viên")


@pytest.fixture
async def asker(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student", "Người Hỏi")


@pytest.fixture
async def classmate(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student", "Bạn Cùng Lớp")


@pytest.fixture
async def course_and_lesson(
    db_session: AsyncSession, owner: User, asker: User, classmate: User
) -> tuple[Course, Lesson]:
    """A published course that both learners are enrolled in."""
    course, _, lesson = await make_course(db_session, owner)
    await enrol(db_session, course, asker)
    await enrol(db_session, course, classmate)
    return course, lesson


def threads_url(lesson: Lesson) -> str:
    return f"/api/v1/lessons/{lesson.id}/qa-threads"


async def ask(
    client: AsyncClient,
    lesson: Lesson,
    headers: dict[str, str],
    title: str = "Vì sao range(5) dừng ở 4?",
    body: str = "Em tưởng range(5) sẽ in ra cả số 5.",
) -> dict:
    response = await client.post(
        threads_url(lesson), json={"title": title, "body": body}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def answer(
    client: AsyncClient,
    thread_id: str,
    headers: dict[str, str],
    body: str = "Vì range dừng trước số cuối.",
) -> dict:
    response = await client.post(
        f"/api/v1/qa-threads/{thread_id}/replies", json={"body": body}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Asking ----------------------------------------------------------------


async def test_an_enrolled_learner_asks_about_a_lesson(
    api_client: AsyncClient, course_and_lesson, asker: User
) -> None:
    course, lesson = course_and_lesson
    headers = await sign_in(api_client, asker)

    body = await ask(api_client, lesson, headers, title="  Vì sao range(5) dừng ở 4?  ")

    assert body["title"] == "Vì sao range(5) dừng ở 4?"
    assert body["author"] == {
        "id": str(asker.id),
        "full_name": "Người Hỏi",
        "avatar_url": None,
    }
    assert body["lesson"] == {"id": str(lesson.id), "title": "Vòng lặp for"}
    assert body["course"]["slug"] == course.slug
    assert body["vote_count"] == 0
    assert body["voted"] is False
    assert body["reply_count"] == 0
    assert body["has_instructor_reply"] is False
    assert body["resolved_at"] is None


async def test_asking_needs_a_sign_in(api_client: AsyncClient, course_and_lesson) -> None:
    _, lesson = course_and_lesson
    response = await api_client.get(threads_url(lesson))
    assert response.status_code == 401


async def test_a_visitor_on_the_free_preview_cannot_read_or_ask(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """The preview lesson is open to watch; its questions belong to the class."""
    course, preview, _ = await make_course(db_session, owner)
    visitor = await make_user(db_session)
    headers = await sign_in(api_client, visitor)

    listed = await api_client.get(threads_url(preview), headers=headers)
    asked = await api_client.post(
        threads_url(preview), json={"title": "Hỏi thử", "body": "Được không?"}, headers=headers
    )

    assert listed.status_code == 403
    assert listed.json()["detail"]["code"] == "NOT_ENROLLED"
    assert asked.status_code == 403


async def test_the_instructor_takes_part_without_enrolling(
    api_client: AsyncClient, course_and_lesson, owner: User
) -> None:
    _, lesson = course_and_lesson
    headers = await sign_in(api_client, owner)

    response = await api_client.get(threads_url(lesson), headers=headers)

    assert response.status_code == 200


async def test_a_course_back_in_draft_is_gone_for_its_learners(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, asker: User
) -> None:
    course, _, lesson = await make_course(db_session, owner, status="draft")
    await enrol(db_session, course, asker)
    headers = await sign_in(api_client, asker)

    response = await api_client.get(threads_url(lesson), headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_an_unknown_lesson_is_404(api_client: AsyncClient, asker: User) -> None:
    headers = await sign_in(api_client, asker)
    response = await api_client.get(f"/api/v1/lessons/{uuid.uuid4()}/qa-threads", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LESSON_NOT_FOUND"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   ", "body": "Có nội dung"},
        {"title": "Có tiêu đề", "body": "\n \n"},
        {"title": "x" * 201, "body": "Có nội dung"},
        {"title": "Có tiêu đề", "body": "x" * 5001},
        {"title": "Thiếu nội dung"},
    ],
)
async def test_a_question_needs_a_title_and_a_body_of_sane_length(
    api_client: AsyncClient, course_and_lesson, asker: User, payload: dict
) -> None:
    _, lesson = course_and_lesson
    headers = await sign_in(api_client, asker)

    response = await api_client.post(threads_url(lesson), json=payload, headers=headers)

    assert response.status_code == 422


# --- The board -------------------------------------------------------------


async def test_the_board_lists_newest_first_or_most_asked_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course_and_lesson,
    asker: User,
    classmate: User,
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    classmate_headers = await sign_in(api_client, classmate)

    older = await ask(api_client, lesson, asker_headers, title="Câu cũ")
    newer = await ask(api_client, lesson, asker_headers, title="Câu mới")
    # Same transaction, same now(): make the order a fact rather than a race.
    await db_session.execute(
        QaThread.__table__.update()
        .where(QaThread.id == uuid.UUID(older["id"]))
        .values(created_at=datetime(2026, 9, 1, tzinfo=UTC))
    )
    await api_client.put(f"/api/v1/qa-threads/{older['id']}/vote", headers=classmate_headers)

    newest = await api_client.get(threads_url(lesson), headers=classmate_headers)
    top = await api_client.get(
        threads_url(lesson), params={"sort": "top"}, headers=classmate_headers
    )

    assert [t["title"] for t in newest.json()["items"]] == ["Câu mới", "Câu cũ"]
    assert [t["title"] for t in top.json()["items"]] == ["Câu cũ", "Câu mới"]
    assert newest.json()["total"] == 2
    by_id = {t["id"]: t for t in top.json()["items"]}
    assert by_id[older["id"]]["vote_count"] == 1
    assert by_id[older["id"]]["voted"] is True
    assert by_id[newer["id"]]["voted"] is False


async def test_the_board_is_paged(api_client: AsyncClient, course_and_lesson, asker: User) -> None:
    _, lesson = course_and_lesson
    headers = await sign_in(api_client, asker)
    for n in range(3):
        await ask(api_client, lesson, headers, title=f"Câu {n}")

    first = await api_client.get(threads_url(lesson), params={"page_size": 2}, headers=headers)
    second = await api_client.get(
        threads_url(lesson), params={"page_size": 2, "page": 2}, headers=headers
    )

    assert first.json()["total"] == 3
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) == 1
    seen = {t["id"] for t in first.json()["items"]} | {t["id"] for t in second.json()["items"]}
    assert len(seen) == 3


async def test_an_unknown_sort_is_422(
    api_client: AsyncClient, course_and_lesson, asker: User
) -> None:
    _, lesson = course_and_lesson
    headers = await sign_in(api_client, asker)
    response = await api_client.get(threads_url(lesson), params={"sort": "votes"}, headers=headers)
    assert response.status_code == 422


# --- Votes -----------------------------------------------------------------


async def test_voting_twice_is_voting_once_and_it_can_be_taken_back(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course_and_lesson,
    asker: User,
    classmate: User,
) -> None:
    _, lesson = course_and_lesson
    thread = await ask(api_client, lesson, await sign_in(api_client, asker))
    headers = await sign_in(api_client, classmate)
    url = f"/api/v1/qa-threads/{thread['id']}/vote"

    assert (await api_client.put(url, headers=headers)).status_code == 204
    assert (await api_client.put(url, headers=headers)).status_code == 204
    votes = await db_session.scalar(
        select(func.count()).select_from(QaVote).where(QaVote.thread_id == uuid.UUID(thread["id"]))
    )
    assert votes == 1

    assert (await api_client.delete(url, headers=headers)).status_code == 204
    assert (await api_client.delete(url, headers=headers)).status_code == 204
    detail = await api_client.get(f"/api/v1/qa-threads/{thread['id']}", headers=headers)
    assert detail.json()["vote_count"] == 0
    assert detail.json()["voted"] is False


async def test_nobody_votes_for_their_own_question(
    api_client: AsyncClient, course_and_lesson, asker: User
) -> None:
    _, lesson = course_and_lesson
    headers = await sign_in(api_client, asker)
    thread = await ask(api_client, lesson, headers)

    response = await api_client.put(f"/api/v1/qa-threads/{thread['id']}/vote", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CANNOT_VOTE_OWN_THREAD"


# --- Replies ---------------------------------------------------------------


async def test_only_the_courses_instructor_wears_the_badge(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course_and_lesson,
    owner: User,
    asker: User,
    classmate: User,
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    thread = await ask(api_client, lesson, asker_headers)

    from_classmate = await answer(api_client, thread["id"], await sign_in(api_client, classmate))
    listed = await api_client.get(threads_url(lesson), headers=asker_headers)
    assert from_classmate["is_instructor_reply"] is False
    assert listed.json()["items"][0]["has_instructor_reply"] is False

    admin = await make_user(db_session, "admin")
    from_admin = await answer(api_client, thread["id"], await sign_in(api_client, admin))
    assert from_admin["is_instructor_reply"] is False

    from_owner = await answer(api_client, thread["id"], await sign_in(api_client, owner))
    listed = await api_client.get(threads_url(lesson), headers=asker_headers)
    assert from_owner["is_instructor_reply"] is True
    assert from_owner["author"]["full_name"] == "Cô Giảng Viên"
    assert listed.json()["items"][0]["has_instructor_reply"] is True
    assert listed.json()["items"][0]["reply_count"] == 3


async def test_replies_read_as_a_conversation_oldest_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course_and_lesson,
    asker: User,
    classmate: User,
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    thread = await ask(api_client, lesson, asker_headers)
    first = await answer(
        api_client, thread["id"], await sign_in(api_client, classmate), "Trả lời trước"
    )
    await answer(api_client, thread["id"], asker_headers, "Cảm ơn bạn")
    await db_session.execute(
        QaReply.__table__.update()
        .where(QaReply.id == uuid.UUID(first["id"]))
        .values(created_at=datetime(2026, 9, 1, tzinfo=UTC))
    )

    response = await api_client.get(
        f"/api/v1/qa-threads/{thread['id']}/replies", headers=asker_headers
    )

    assert response.status_code == 200
    assert [r["body"] for r in response.json()["items"]] == ["Trả lời trước", "Cảm ơn bạn"]
    assert response.json()["total"] == 2


async def test_a_blank_reply_is_422(
    api_client: AsyncClient, course_and_lesson, asker: User
) -> None:
    _, lesson = course_and_lesson
    headers = await sign_in(api_client, asker)
    thread = await ask(api_client, lesson, headers)

    response = await api_client.post(
        f"/api/v1/qa-threads/{thread['id']}/replies", json={"body": "   "}, headers=headers
    )

    assert response.status_code == 422


async def test_an_outsider_cannot_answer(
    api_client: AsyncClient, db_session: AsyncSession, course_and_lesson, asker: User
) -> None:
    _, lesson = course_and_lesson
    thread = await ask(api_client, lesson, await sign_in(api_client, asker))
    outsider = await make_user(db_session)

    response = await api_client.post(
        f"/api/v1/qa-threads/{thread['id']}/replies",
        json={"body": "Mình biết nè"},
        headers=await sign_in(api_client, outsider),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_ENROLLED"


async def test_an_unknown_thread_is_404(api_client: AsyncClient, asker: User) -> None:
    headers = await sign_in(api_client, asker)
    response = await api_client.get(f"/api/v1/qa-threads/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "QA_THREAD_NOT_FOUND"


# --- Notifications ---------------------------------------------------------


async def test_the_asker_is_told_when_somebody_answers(
    api_client: AsyncClient, db_session: AsyncSession, course_and_lesson, owner: User, asker: User
) -> None:
    course, lesson = course_and_lesson
    thread = await ask(api_client, lesson, await sign_in(api_client, asker))

    reply = await answer(api_client, thread["id"], await sign_in(api_client, owner))

    notifications = list(
        await db_session.scalars(select(Notification).where(Notification.user_id == asker.id))
    )
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.type == "qa_reply"
    assert notification.read_at is None
    assert notification.payload == {
        "thread_id": thread["id"],
        "reply_id": reply["id"],
        "lesson_id": str(lesson.id),
        "course_id": str(course.id),
        "course_slug": course.slug,
        "thread_title": thread["title"],
        "replier_name": "Cô Giảng Viên",
        "is_instructor_reply": True,
    }


async def test_answering_your_own_question_tells_nobody(
    api_client: AsyncClient, db_session: AsyncSession, course_and_lesson, asker: User
) -> None:
    _, lesson = course_and_lesson
    headers = await sign_in(api_client, asker)
    thread = await ask(api_client, lesson, headers)

    await answer(api_client, thread["id"], headers, "À em hiểu rồi")

    # Asking told the instructor (`qa_question`); answering it yourself tells
    # nobody anything more.
    count = await db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.type == "qa_reply",
            Notification.payload["thread_id"].astext == thread["id"],
        )
    )
    assert count == 0


# --- Changing and removing -------------------------------------------------


async def test_only_the_asker_edits_the_question(
    api_client: AsyncClient, course_and_lesson, owner: User, asker: User, classmate: User
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    thread = await ask(api_client, lesson, asker_headers)
    url = f"/api/v1/qa-threads/{thread['id']}"

    edited = await api_client.patch(url, json={"title": "Sửa lại tiêu đề"}, headers=asker_headers)
    by_classmate = await api_client.patch(
        url, json={"body": "Sửa hộ"}, headers=await sign_in(api_client, classmate)
    )
    by_owner = await api_client.patch(
        url, json={"title": "Giảng viên sửa"}, headers=await sign_in(api_client, owner)
    )

    assert edited.status_code == 200
    assert edited.json()["title"] == "Sửa lại tiêu đề"
    assert edited.json()["body"] == thread["body"]
    assert by_classmate.status_code == 403
    assert by_classmate.json()["detail"]["code"] == "QA_NOT_ALLOWED"
    assert by_owner.status_code == 403


async def test_the_asker_or_the_instructor_marks_it_resolved(
    api_client: AsyncClient, course_and_lesson, owner: User, asker: User, classmate: User
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    thread = await ask(api_client, lesson, asker_headers)
    url = f"/api/v1/qa-threads/{thread['id']}"

    by_classmate = await api_client.patch(
        url, json={"resolved": True}, headers=await sign_in(api_client, classmate)
    )
    by_owner = await api_client.patch(
        url, json={"resolved": True}, headers=await sign_in(api_client, owner)
    )
    again = await api_client.patch(url, json={"resolved": True}, headers=asker_headers)
    reopened = await api_client.patch(url, json={"resolved": False}, headers=asker_headers)

    assert by_classmate.status_code == 403
    assert by_owner.status_code == 200
    assert by_owner.json()["resolved_at"] is not None
    # Saying "solved" a second time keeps the first time it was said.
    assert again.json()["resolved_at"] == by_owner.json()["resolved_at"]
    assert reopened.json()["resolved_at"] is None


async def test_a_request_that_may_do_only_half_does_neither(
    api_client: AsyncClient, course_and_lesson, owner: User, asker: User
) -> None:
    """The instructor may resolve but not reword: asking for both changes nothing."""
    _, lesson = course_and_lesson
    thread = await ask(api_client, lesson, await sign_in(api_client, asker))
    owner_headers = await sign_in(api_client, owner)

    response = await api_client.patch(
        f"/api/v1/qa-threads/{thread['id']}",
        json={"title": "Đổi tên", "resolved": True},
        headers=owner_headers,
    )
    after = await api_client.get(f"/api/v1/qa-threads/{thread['id']}", headers=owner_headers)

    assert response.status_code == 403
    assert after.json()["title"] == thread["title"]
    assert after.json()["resolved_at"] is None


async def test_deleting_a_question_takes_its_answers_and_votes(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course_and_lesson,
    owner: User,
    asker: User,
    classmate: User,
) -> None:
    _, lesson = course_and_lesson
    thread = await ask(api_client, lesson, await sign_in(api_client, asker))
    classmate_headers = await sign_in(api_client, classmate)
    await answer(api_client, thread["id"], classmate_headers)
    await api_client.put(f"/api/v1/qa-threads/{thread['id']}/vote", headers=classmate_headers)
    url = f"/api/v1/qa-threads/{thread['id']}"

    by_classmate = await api_client.delete(url, headers=classmate_headers)
    by_owner = await api_client.delete(url, headers=await sign_in(api_client, owner))

    assert by_classmate.status_code == 403
    assert by_owner.status_code == 204
    thread_id = uuid.UUID(thread["id"])
    assert await db_session.get(QaThread, thread_id) is None
    for model in (QaReply, QaVote):
        left = await db_session.scalar(
            select(func.count()).select_from(model).where(model.thread_id == thread_id)
        )
        assert left == 0


async def test_a_reply_is_removed_by_its_author_or_the_staff(
    api_client: AsyncClient, course_and_lesson, owner: User, asker: User, classmate: User
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    classmate_headers = await sign_in(api_client, classmate)
    thread = await ask(api_client, lesson, asker_headers)
    mine = await answer(api_client, thread["id"], classmate_headers, "Của mình")
    theirs = await answer(api_client, thread["id"], asker_headers, "Của người hỏi")

    not_mine = await api_client.delete(
        f"/api/v1/qa-replies/{theirs['id']}", headers=classmate_headers
    )
    own = await api_client.delete(f"/api/v1/qa-replies/{mine['id']}", headers=classmate_headers)
    by_owner = await api_client.delete(
        f"/api/v1/qa-replies/{theirs['id']}", headers=await sign_in(api_client, owner)
    )
    gone = await api_client.delete(f"/api/v1/qa-replies/{theirs['id']}", headers=asker_headers)

    assert not_mine.status_code == 403
    assert own.status_code == 204
    assert by_owner.status_code == 204
    assert gone.status_code == 404
    assert gone.json()["detail"]["code"] == "QA_REPLY_NOT_FOUND"


# --- The instructor's inbox ------------------------------------------------


async def test_the_inbox_holds_only_the_instructors_own_courses(
    api_client: AsyncClient, db_session: AsyncSession, course_and_lesson, owner: User, asker: User
) -> None:
    course, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    mine = await ask(api_client, lesson, asker_headers, title="Câu ở khóa của tôi")

    other_owner = await make_user(db_session, "instructor")
    other_course, _, other_lesson = await make_course(db_session, other_owner)
    await enrol(db_session, other_course, asker)
    await ask(api_client, other_lesson, asker_headers, title="Câu ở khóa người khác")

    response = await api_client.get(
        "/api/v1/instructor/qa-threads", headers=await sign_in(api_client, owner)
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [t["id"] for t in items] == [mine["id"]]
    assert items[0]["course"] == {"id": str(course.id), "title": course.title, "slug": course.slug}
    assert items[0]["lesson"]["title"] == "Vòng lặp for"


async def test_unanswered_means_no_instructor_reply_and_not_resolved(
    api_client: AsyncClient, course_and_lesson, owner: User, asker: User, classmate: User
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    owner_headers = await sign_in(api_client, owner)
    waiting = await ask(api_client, lesson, asker_headers, title="Chưa ai trả lời")
    peer_answered = await ask(api_client, lesson, asker_headers, title="Bạn học trả lời")
    answered = await ask(api_client, lesson, asker_headers, title="Giảng viên trả lời")
    solved = await ask(api_client, lesson, asker_headers, title="Tự giải quyết")
    await answer(api_client, peer_answered["id"], await sign_in(api_client, classmate))
    await answer(api_client, answered["id"], owner_headers)
    await api_client.patch(
        f"/api/v1/qa-threads/{solved['id']}", json={"resolved": True}, headers=asker_headers
    )

    response = await api_client.get(
        "/api/v1/instructor/qa-threads", params={"unanswered": True}, headers=owner_headers
    )

    assert {t["id"] for t in response.json()["items"]} == {waiting["id"], peer_answered["id"]}
    assert response.json()["total"] == 2


async def test_the_inbox_narrows_to_one_course(
    api_client: AsyncClient, db_session: AsyncSession, course_and_lesson, owner: User, asker: User
) -> None:
    _, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    await ask(api_client, lesson, asker_headers, title="Khóa một")
    second_course, _, second_lesson = await make_course(db_session, owner)
    await enrol(db_session, second_course, asker)
    other = await ask(api_client, second_lesson, asker_headers, title="Khóa hai")

    response = await api_client.get(
        "/api/v1/instructor/qa-threads",
        params={"course_id": str(second_course.id)},
        headers=await sign_in(api_client, owner),
    )

    assert [t["id"] for t in response.json()["items"]] == [other["id"]]


async def test_the_inbox_is_for_instructors(api_client: AsyncClient, asker: User) -> None:
    response = await api_client.get(
        "/api/v1/instructor/qa-threads", headers=await sign_in(api_client, asker)
    )
    assert response.status_code == 403
