"""The notification bell and its page.

What matters: a person only ever sees and touches their own notifications;
"read" is idempotent and remembers the first time; and the two Q&A events
really arrive at the other end -- the instructor hears about a question, the
asker about its answer.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, User
from app.services import notifications as notifications_service
from tests.api.test_qa import answer, ask, enrol, make_course, make_user, sign_in

URL = "/api/v1/notifications"
T0 = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)


async def notify(
    session: AsyncSession,
    user: User,
    *,
    minutes: int = 0,
    read: bool = False,
    title: str = "Câu hỏi",
) -> Notification:
    """A `qa_reply` row written straight to the table, at a chosen moment."""
    notification = Notification(
        user_id=user.id,
        type="qa_reply",
        payload={"thread_title": title},
        created_at=T0 + timedelta(minutes=minutes),
        read_at=T0 + timedelta(minutes=minutes, seconds=30) if read else None,
    )
    session.add(notification)
    await session.flush()
    return notification


@pytest.fixture
async def reader(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student", "Người Đọc")


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor", "Cô Giảng Viên")


@pytest.fixture
async def asker(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student", "Người Hỏi")


@pytest.fixture
async def course_and_lesson(db_session: AsyncSession, owner: User, asker: User):
    course, _, lesson = await make_course(db_session, owner)
    await enrol(db_session, course, asker)
    return course, lesson


# --- Reading ---------------------------------------------------------------


async def test_the_list_is_mine_and_newest_first(
    api_client: AsyncClient, db_session: AsyncSession, reader: User
) -> None:
    stranger = await make_user(db_session)
    await notify(db_session, reader, minutes=0, title="cũ")
    await notify(db_session, reader, minutes=5, title="mới", read=True)
    await notify(db_session, stranger, minutes=10, title="của người khác")

    response = await api_client.get(URL, headers=await sign_in(api_client, reader))

    assert response.status_code == 200
    body = response.json()
    assert [n["payload"]["thread_title"] for n in body["items"]] == ["mới", "cũ"]
    assert body["total"] == 2
    assert body["items"][0]["type"] == "qa_reply"
    assert body["items"][0]["read_at"] is not None
    assert body["items"][1]["read_at"] is None


async def test_unread_only_and_the_count_on_the_bell(
    api_client: AsyncClient, db_session: AsyncSession, reader: User
) -> None:
    await notify(db_session, reader, minutes=0)
    await notify(db_session, reader, minutes=1)
    await notify(db_session, reader, minutes=2, read=True)
    headers = await sign_in(api_client, reader)

    unread = await api_client.get(URL, params={"unread": True}, headers=headers)
    count = await api_client.get(f"{URL}/unread-count", headers=headers)

    assert unread.json()["total"] == 2
    assert all(n["read_at"] is None for n in unread.json()["items"])
    assert count.json() == {"count": 2}


async def test_the_list_is_paged(
    api_client: AsyncClient, db_session: AsyncSession, reader: User
) -> None:
    for minute in range(3):
        await notify(db_session, reader, minutes=minute)
    headers = await sign_in(api_client, reader)

    second = await api_client.get(URL, params={"page": 2, "page_size": 2}, headers=headers)

    assert second.json()["total"] == 3
    assert len(second.json()["items"]) == 1


async def test_notifications_need_a_sign_in(api_client: AsyncClient) -> None:
    assert (await api_client.get(URL)).status_code == 401
    assert (await api_client.get(f"{URL}/unread-count")).status_code == 401
    assert (await api_client.post(f"{URL}/read-all")).status_code == 401


# --- Marking as read -------------------------------------------------------


async def test_reading_one_keeps_the_first_time_it_was_read(
    api_client: AsyncClient, db_session: AsyncSession, reader: User
) -> None:
    notification = await notify(db_session, reader)
    headers = await sign_in(api_client, reader)

    first = await api_client.post(f"{URL}/{notification.id}/read", headers=headers)
    await db_session.refresh(notification)
    read_at = notification.read_at
    again = await api_client.post(f"{URL}/{notification.id}/read", headers=headers)
    await db_session.refresh(notification)

    assert first.status_code == 204
    assert again.status_code == 204
    assert read_at is not None
    assert notification.read_at == read_at
    count = await api_client.get(f"{URL}/unread-count", headers=headers)
    assert count.json() == {"count": 0}


async def test_somebody_elses_notification_is_404(
    api_client: AsyncClient, db_session: AsyncSession, reader: User
) -> None:
    stranger = await make_user(db_session)
    theirs = await notify(db_session, stranger)
    headers = await sign_in(api_client, reader)

    response = await api_client.post(f"{URL}/{theirs.id}/read", headers=headers)
    unknown = await api_client.post(f"{URL}/{uuid.uuid4()}/read", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOTIFICATION_NOT_FOUND"
    assert unknown.status_code == 404
    await db_session.refresh(theirs)
    assert theirs.read_at is None


async def test_read_all_touches_only_mine_and_only_the_unread(
    api_client: AsyncClient, db_session: AsyncSession, reader: User
) -> None:
    stranger = await make_user(db_session)
    already = await notify(db_session, reader, minutes=0, read=True)
    first_read = already.read_at
    await notify(db_session, reader, minutes=1)
    await notify(db_session, reader, minutes=2)
    theirs = await notify(db_session, stranger, minutes=3)
    headers = await sign_in(api_client, reader)

    response = await api_client.post(f"{URL}/read-all", headers=headers)
    again = await api_client.post(f"{URL}/read-all", headers=headers)

    assert response.json() == {"marked": 2}
    assert again.json() == {"marked": 0}
    await db_session.refresh(already)
    await db_session.refresh(theirs)
    assert already.read_at == first_read
    assert theirs.read_at is None


def test_an_unknown_type_is_refused_before_it_reaches_the_table(
    db_session: AsyncSession, reader: User
) -> None:
    with pytest.raises(ValueError):
        notifications_service.add(db_session, user_id=reader.id, type="nope", payload={})


# --- The two Q&A events, end to end ----------------------------------------


async def test_the_instructor_hears_about_a_question_and_the_asker_about_its_answer(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course_and_lesson,
    owner: User,
    asker: User,
) -> None:
    course, lesson = course_and_lesson
    asker_headers = await sign_in(api_client, asker)
    owner_headers = await sign_in(api_client, owner)

    thread = await ask(api_client, lesson, asker_headers)
    for_owner = (await api_client.get(URL, headers=owner_headers)).json()["items"]

    assert [n["type"] for n in for_owner] == ["qa_question"]
    assert for_owner[0]["payload"] == {
        "thread_id": thread["id"],
        "lesson_id": str(lesson.id),
        "course_id": str(course.id),
        "course_title": course.title,
        "lesson_title": lesson.title,
        "thread_title": thread["title"],
        "asker_name": "Người Hỏi",
    }

    await answer(api_client, thread["id"], owner_headers)
    for_asker = (await api_client.get(URL, headers=asker_headers)).json()["items"]
    assert [n["type"] for n in for_asker] == ["qa_reply"]
    assert (await api_client.get(f"{URL}/unread-count", headers=asker_headers)).json() == {
        "count": 1
    }


async def test_the_instructor_asking_in_their_own_course_notifies_nobody(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course_and_lesson,
    owner: User,
) -> None:
    _, lesson = course_and_lesson

    await ask(api_client, lesson, await sign_in(api_client, owner), title="Thông báo lịch học")

    rows = list(await db_session.scalars(select(Notification)))
    assert rows == []
