"""Reports: filing one, and the admin deciding it.

What must hold, in the order a report lives through it: you can report only
what you can see and did not write; one pending report per person per target;
the admin sees the content as it is now; and a decision closes every pending
report on that content -- taking it down, when asked, in the same transaction.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Course,
    Lesson,
    Notification,
    QaReply,
    QaThread,
    Report,
    Review,
    User,
)
from app.services import course_stats
from tests.api.publishing import admin_headers
from tests.api.test_qa import answer, ask, enrol, make_course, make_user, sign_in

REPORTS = "/api/v1/reports"
ADMIN = "/api/v1/admin/reports"


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor", "Cô Giảng Viên")


@pytest.fixture
async def writer(db_session: AsyncSession) -> User:
    """Wrote the thing that gets reported."""
    return await make_user(db_session, "student", "Người Viết")


@pytest.fixture
async def reporter(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student", "Người Báo Cáo")


@pytest.fixture
async def classroom(
    db_session: AsyncSession, owner: User, writer: User, reporter: User
) -> tuple[Course, Lesson]:
    """A published course both learners are enrolled in."""
    course, _, lesson = await make_course(db_session, owner)
    await enrol(db_session, course, writer)
    await enrol(db_session, course, reporter)
    return course, lesson


@pytest.fixture
async def admin(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await admin_headers(api_client, db_session)


async def write_review(
    session: AsyncSession, course: Course, user: User, rating: int, comment: str = "Tệ"
) -> Review:
    review = Review(course_id=course.id, user_id=user.id, rating=rating, comment=comment)
    session.add(review)
    await session.flush()
    await course_stats.recount_rating(session, course.id)
    return review


async def file(
    client: AsyncClient,
    headers: dict[str, str],
    target_type: str,
    target_id,
    reason: str = "spam",
    details: str | None = None,
):
    return await client.post(
        REPORTS,
        json={
            "target_type": target_type,
            "target_id": str(target_id),
            "reason": reason,
            "details": details,
        },
        headers=headers,
    )


async def filed(client: AsyncClient, user: User, target_type: str, target_id) -> dict:
    response = await file(client, await sign_in(client, user), target_type, target_id)
    assert response.status_code == 201, response.text
    return response.json()


# --- Filing ----------------------------------------------------------------


async def test_reporting_needs_an_account(api_client: AsyncClient, classroom) -> None:
    course, _ = classroom
    response = await api_client.post(
        REPORTS, json={"target_type": "course", "target_id": str(course.id), "reason": "spam"}
    )
    assert response.status_code == 401


async def test_a_learner_reports_a_course(
    api_client: AsyncClient, classroom, reporter: User
) -> None:
    course, _ = classroom

    response = await file(
        api_client,
        await sign_in(api_client, reporter),
        "course",
        course.id,
        reason="copyright",
        details="  Chép nguyên từ một khóa khác  ",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "open"
    assert body["reason"] == "copyright"
    assert body["details"] == "Chép nguyên từ một khóa khác"


async def test_a_visitor_account_may_report_a_public_course(
    api_client: AsyncClient, db_session: AsyncSession, classroom
) -> None:
    """A course on sale is public; you need not have bought it to flag it."""
    course, _ = classroom
    stranger = await make_user(db_session, "student", "Người Lạ")

    await filed(api_client, stranger, "course", course.id)


async def test_nobody_reports_their_own_words(
    api_client: AsyncClient, db_session: AsyncSession, classroom, owner: User, writer: User
) -> None:
    course, lesson = classroom
    review = await write_review(db_session, course, writer, 1)
    thread = await ask(api_client, lesson, await sign_in(api_client, writer))

    cases = [(owner, "course", course.id), (writer, "review", review.id)]
    cases.append((writer, "qa_thread", thread["id"]))
    for user, target_type, target_id in cases:
        response = await file(api_client, await sign_in(api_client, user), target_type, target_id)
        assert response.status_code == 409, target_type
        assert response.json()["detail"]["code"] == "CANNOT_REPORT_OWN_CONTENT"


async def test_what_you_cannot_see_you_cannot_report(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, reporter: User
) -> None:
    draft, _, _ = await make_course(db_session, owner, status="draft")
    headers = await sign_in(api_client, reporter)

    for target_type, target_id in (
        ("course", draft.id),
        ("course", uuid.uuid4()),
        ("review", uuid.uuid4()),
        ("qa_thread", uuid.uuid4()),
        ("qa_reply", uuid.uuid4()),
    ):
        response = await file(api_client, headers, target_type, target_id)
        assert response.status_code == 404, target_type
        assert response.json()["detail"]["code"] == "REPORT_TARGET_NOT_FOUND"


async def test_a_question_is_reported_only_from_inside_the_class(
    api_client: AsyncClient, db_session: AsyncSession, classroom, writer: User
) -> None:
    _, lesson = classroom
    thread = await ask(api_client, lesson, await sign_in(api_client, writer))
    outsider = await make_user(db_session, "student", "Ngoài Lớp")

    headers = await sign_in(api_client, outsider)

    response = await file(api_client, headers, "qa_thread", thread["id"])

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_ENROLLED"


async def test_one_pending_report_per_person_per_target(
    api_client: AsyncClient, classroom, reporter: User, admin: dict[str, str]
) -> None:
    course, _ = classroom
    first = await filed(api_client, reporter, "course", course.id)

    again = await file(api_client, await sign_in(api_client, reporter), "course", course.id)
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "ALREADY_REPORTED"

    # Once decided, the same person may flag it again.
    await api_client.post(f"{ADMIN}/{first['id']}/dismiss", json={}, headers=admin)
    await filed(api_client, reporter, "course", course.id)


@pytest.mark.parametrize(
    "body",
    [
        {"reason": "other"},
        {"reason": "other", "details": "   "},
        {"reason": "khong-ro"},
        {"reason": "spam", "target_type": "lesson"},
        {"reason": "spam", "details": "x" * 1001},
    ],
)
async def test_a_report_the_admin_could_not_act_on_is_a_422(
    api_client: AsyncClient, classroom, reporter: User, body: dict
) -> None:
    course, _ = classroom
    payload = {"target_type": "course", "target_id": str(course.id), **body}

    response = await api_client.post(
        REPORTS, json=payload, headers=await sign_in(api_client, reporter)
    )

    assert response.status_code == 422


# --- The admin's queue -----------------------------------------------------


async def test_only_an_admin_reads_the_queue(
    api_client: AsyncClient, reporter: User, owner: User
) -> None:
    assert (await api_client.get(ADMIN)).status_code == 401
    for user in (reporter, owner):
        response = await api_client.get(ADMIN, headers=await sign_in(api_client, user))
        assert response.status_code == 403


async def test_the_queue_shows_the_content_as_it_is_now(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    writer: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    course, lesson = classroom
    thread = await ask(api_client, lesson, await sign_in(api_client, writer), title="Câu hỏi rác")
    second = await make_user(db_session, "student", "Người Thứ Hai")
    await enrol(db_session, course, second)
    report = await filed(api_client, reporter, "qa_thread", thread["id"])
    await filed(api_client, second, "qa_thread", thread["id"])

    response = await api_client.get(ADMIN, params={"target_type": "qa_thread"}, headers=admin)

    assert response.status_code == 200
    item = next(i for i in response.json()["items"] if i["id"] == report["id"])
    assert item["reporter"]["email"] == reporter.email
    assert item["pending_on_target"] == 2
    target = item["target"]
    assert target["exists"] is True
    assert target["title"] == "Câu hỏi rác"
    assert target["author"]["id"] == str(writer.id)
    assert target["course"]["slug"] == course.slug
    assert target["lesson_id"] == str(lesson.id)
    assert target["thread_id"] == thread["id"]


async def test_the_queue_is_oldest_first_and_says_when_content_is_gone(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    writer: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    course, _ = classroom
    review = await write_review(db_session, course, writer, 1)
    older = await filed(api_client, reporter, "review", review.id)
    newer = await filed(api_client, reporter, "course", course.id)
    # Inside one test transaction `now()` is one instant; say which came first.
    early = await db_session.get(Report, uuid.UUID(older["id"]))
    early.created_at = early.created_at - timedelta(hours=1)
    # The author withdraws the review before any admin looks.
    await db_session.delete(review)
    await db_session.flush()

    items = (await api_client.get(ADMIN, headers=admin)).json()["items"]
    ids = [item["id"] for item in items]

    assert ids.index(older["id"]) < ids.index(newer["id"])
    gone = next(item for item in items if item["id"] == older["id"])
    assert gone["target"]["exists"] is False
    assert gone["target"]["author"] is None


async def test_marking_a_report_as_under_review(
    api_client: AsyncClient, classroom, reporter: User, admin: dict[str, str]
) -> None:
    course, _ = classroom
    report = await filed(api_client, reporter, "course", course.id)

    response = await api_client.post(f"{ADMIN}/{report['id']}/review", headers=admin)

    assert response.status_code == 200
    assert response.json()["status"] == "reviewing"


# --- Deciding --------------------------------------------------------------


async def test_resolving_with_removal_deletes_a_review_and_recounts_the_rating(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    writer: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    course, _ = classroom
    fair = await make_user(db_session, "student", "Đánh Giá Công Bằng")
    await enrol(db_session, course, fair)
    await write_review(db_session, course, fair, 5, "Hay")
    abusive = await write_review(db_session, course, writer, 1, "Chửi bới")
    first = await filed(api_client, reporter, "review", abusive.id)
    second = await filed(api_client, fair, "review", abusive.id)

    response = await api_client.post(
        f"{ADMIN}/{first['id']}/resolve",
        json={"note": "Ngôn từ xúc phạm", "remove_content": True},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "resolved"
    assert body["content_removed"] is True
    assert body["resolution_note"] == "Ngôn từ xúc phạm"
    assert body["resolved_by"] is not None
    assert body["pending_on_target"] == 0
    assert await db_session.get(Review, abusive.id) is None
    await db_session.refresh(course)
    assert course.rating_count == 1
    assert course.rating_avg == Decimal("5.00")
    # The other reporter's report closed with the same decision.
    other = await db_session.get(Report, uuid.UUID(second["id"]))
    await db_session.refresh(other)
    assert other.status == "resolved"
    assert other.content_removed is True


async def test_resolving_with_removal_takes_a_course_down_and_tells_its_instructor(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    owner: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    course, _ = classroom
    report = await filed(api_client, reporter, "course", course.id)

    response = await api_client.post(
        f"{ADMIN}/{report['id']}/resolve", json={"remove_content": True}, headers=admin
    )

    assert response.json()["content_removed"] is True
    await db_session.refresh(course)
    assert course.status == "draft"
    assert course.deleted_at is None
    notification = await db_session.scalar(
        select(Notification).where(
            Notification.user_id == owner.id, Notification.type == "course_taken_down"
        )
    )
    assert notification is not None
    assert notification.payload["reason"]  # the default wording, since no note was given


async def test_resolving_with_removal_deletes_a_question_with_its_answers(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    owner: User,
    writer: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    _, lesson = classroom
    thread = await ask(api_client, lesson, await sign_in(api_client, writer))
    reply = await answer(api_client, thread["id"], await sign_in(api_client, owner))
    report = await filed(api_client, reporter, "qa_thread", thread["id"])

    await api_client.post(
        f"{ADMIN}/{report['id']}/resolve", json={"remove_content": True}, headers=admin
    )

    assert await db_session.get(QaThread, uuid.UUID(thread["id"])) is None
    assert await db_session.get(QaReply, uuid.UUID(reply["id"])) is None


async def test_resolving_with_removal_deletes_just_the_reply(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    owner: User,
    writer: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    _, lesson = classroom
    thread = await ask(api_client, lesson, await sign_in(api_client, reporter))
    reply = await answer(api_client, thread["id"], await sign_in(api_client, writer))
    report = await filed(api_client, reporter, "qa_reply", reply["id"])

    await api_client.post(
        f"{ADMIN}/{report['id']}/resolve", json={"remove_content": True}, headers=admin
    )

    assert await db_session.get(QaReply, uuid.UUID(reply["id"])) is None
    assert await db_session.get(QaThread, uuid.UUID(thread["id"])) is not None


async def test_resolving_without_removal_leaves_the_content(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    writer: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    course, _ = classroom
    review = await write_review(db_session, course, writer, 2)
    report = await filed(api_client, reporter, "review", review.id)

    response = await api_client.post(f"{ADMIN}/{report['id']}/resolve", json={}, headers=admin)

    assert response.json()["status"] == "resolved"
    assert response.json()["content_removed"] is False
    assert await db_session.get(Review, review.id) is not None


async def test_removing_content_that_is_already_gone_records_nothing_removed(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    writer: User,
    reporter: User,
    admin: dict[str, str],
) -> None:
    course, _ = classroom
    review = await write_review(db_session, course, writer, 1)
    report = await filed(api_client, reporter, "review", review.id)
    await db_session.delete(review)
    await db_session.flush()

    response = await api_client.post(
        f"{ADMIN}/{report['id']}/resolve", json={"remove_content": True}, headers=admin
    )

    assert response.status_code == 200
    assert response.json()["content_removed"] is False


async def test_dismissing_closes_every_pending_report_and_keeps_the_content(
    api_client: AsyncClient,
    db_session: AsyncSession,
    classroom,
    owner: User,
    reporter: User,
    writer: User,
    admin: dict[str, str],
) -> None:
    course, _ = classroom
    first = await filed(api_client, reporter, "course", course.id)
    await filed(api_client, writer, "course", course.id)

    response = await api_client.post(
        f"{ADMIN}/{first['id']}/dismiss", json={"note": "Không vi phạm"}, headers=admin
    )

    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    await db_session.refresh(course)
    assert course.status == "published"
    pending = await db_session.scalar(
        select(Report).where(Report.target_id == course.id, Report.status == "open")
    )
    assert pending is None

    closed = (await api_client.get(ADMIN, params={"status": "closed"}, headers=admin)).json()
    assert any(item["id"] == first["id"] for item in closed["items"])


async def test_a_decided_report_cannot_be_decided_again(
    api_client: AsyncClient, classroom, reporter: User, admin: dict[str, str]
) -> None:
    course, _ = classroom
    report = await filed(api_client, reporter, "course", course.id)
    await api_client.post(f"{ADMIN}/{report['id']}/dismiss", json={}, headers=admin)

    for action, body in (("resolve", {}), ("dismiss", {}), ("review", None)):
        url = f"{ADMIN}/{report['id']}/{action}"
        response = await api_client.post(url, json=body, headers=admin)
        assert response.status_code == 409, action
        assert response.json()["detail"]["code"] == "REPORT_ALREADY_CLOSED"


async def test_an_unknown_report_is_a_404(api_client: AsyncClient, admin: dict[str, str]) -> None:
    response = await api_client.post(f"{ADMIN}/{uuid.uuid4()}/dismiss", json={}, headers=admin)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REPORT_NOT_FOUND"
