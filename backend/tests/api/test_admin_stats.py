"""The admin's platform dashboard: revenue, active users, hot courses.

The numbers are worked out over a window ending on a chosen day in 2031, so
the rows each test writes are the only ones inside it -- the dev database has
two years of seeded activity, CI has none, and both must give the same answer.
"""

import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import VIETNAM
from app.models import (
    ChatMessage,
    ChatSession,
    Course,
    Enrollment,
    LessonProgress,
    RefreshToken,
    User,
)
from app.services import platform_stats
from tests.api.publishing import admin_headers
from tests.api.test_commerce import make_course, make_user, sign_in
from tests.api.test_instructor_stats import add_lessons, sell

TODAY = date(2031, 6, 15)
NOW = datetime.combine(TODAY, time(18, 0), VIETNAM)


def at(day: date, hour: int = 12) -> datetime:
    return datetime.combine(day, time(hour), VIETNAM)


def day(offset: int) -> date:
    """`offset` days before TODAY."""
    return TODAY - timedelta(days=offset)


async def enrol(session: AsyncSession, user: User, course: Course, when: datetime) -> Enrollment:
    enrollment = Enrollment(user_id=user.id, course_id=course.id, source="free", created_at=when)
    session.add(enrollment)
    await session.flush()
    return enrollment


async def signed_in_at(session: AsyncSession, user: User, when: datetime) -> None:
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=secrets.token_hex(32),
            expires_at=when + timedelta(days=7),
            created_at=when,
        )
    )
    await session.flush()


def point(overview, when: date):
    return next(p for p in overview.series if p.bucket == when)


@pytest.fixture
async def teacher(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


# --- Who may ---------------------------------------------------------------


async def test_only_an_admin_reads_the_dashboard(
    api_client: AsyncClient, db_session: AsyncSession, teacher: User
) -> None:
    for url in ("/api/v1/admin/stats/overview", "/api/v1/admin/stats/hot-courses"):
        assert (await api_client.get(url)).status_code == 401
        response = await api_client.get(url, headers=await sign_in(api_client, teacher))
        assert response.status_code == 403


async def test_the_overview_has_one_point_per_bucket(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await admin_headers(api_client, db_session)

    week = await api_client.get(
        "/api/v1/admin/stats/overview", params={"period": "7d"}, headers=headers
    )
    year = await api_client.get(
        "/api/v1/admin/stats/overview", params={"period": "12m"}, headers=headers
    )
    wrong = await api_client.get(
        "/api/v1/admin/stats/overview", params={"period": "2w"}, headers=headers
    )

    assert week.status_code == 200
    assert week.json()["granularity"] == "day"
    assert len(week.json()["series"]) == 7
    assert {"revenue", "orders", "active_users", "avg_daily_active"} <= set(
        week.json()["current"]
    )
    assert len(year.json()["series"]) == 12
    assert year.json()["granularity"] == "month"
    assert wrong.status_code == 422


# --- Revenue ---------------------------------------------------------------


async def test_revenue_is_what_paid_orders_took_on_the_day_they_were_paid(
    db_session: AsyncSession, teacher: User
) -> None:
    buyer = await make_user(db_session)
    course = await make_course(db_session, teacher, price="300000")

    await sell(db_session, buyer, [(course, "300000", "50000")], paid_at=at(day(5)))
    # 23:30 in Hà Nội is 16:30 UTC: still the Vietnamese day it happened on.
    await sell(db_session, buyer, [(course, "300000", "0")], paid_at=at(day(1), 23))
    await sell(db_session, buyer, [(course, "300000", "0")], paid_at=None, status="pending")
    await sell(db_session, buyer, [(course, "300000", "0")], paid_at=at(day(9)))

    overview = await platform_stats.overview(db_session, "7d", now=NOW)

    assert overview.current.revenue == Decimal("550000.00")
    assert overview.current.orders == 2
    assert point(overview, day(5)).revenue == Decimal("250000.00")
    assert point(overview, day(1)).revenue == Decimal("300000.00")
    assert overview.previous.revenue == Decimal("300000.00")
    assert overview.previous.orders == 1


# --- Active users ----------------------------------------------------------


async def test_a_person_is_active_once_a_day_whatever_they_did(
    db_session: AsyncSession, teacher: User
) -> None:
    course = await make_course(db_session, teacher)
    browsing = await make_user(db_session)
    asking = await make_user(db_session)
    studying = await make_user(db_session)

    # Signed in and enrolled on the same day: one person, one day.
    await signed_in_at(db_session, browsing, at(day(5), 8))
    await enrol(db_session, browsing, course, at(day(5), 9))

    # Asked the AI assistant; its answer the next day is not the learner acting.
    chat = ChatSession(user_id=asking.id, course_id=course.id)
    db_session.add(chat)
    await db_session.flush()
    db_session.add_all(
        [
            ChatMessage(session_id=chat.id, role="user", content="?", created_at=at(day(5))),
            ChatMessage(
                session_id=chat.id, role="assistant", content="!", created_at=at(day(4))
            ),
        ]
    )

    # Progress carries no user of its own; it is found through the enrolment.
    enrolment = await enrol(db_session, studying, course, at(day(20)))
    [lesson] = await add_lessons(db_session, course, 1)
    db_session.add(
        LessonProgress(
            enrollment_id=enrolment.id,
            lesson_id=lesson.id,
            created_at=at(day(3)),
            updated_at=at(day(3)),
        )
    )
    await db_session.flush()

    overview = await platform_stats.overview(db_session, "7d", now=NOW)

    assert point(overview, day(5)).active_users == 2
    assert point(overview, day(4)).active_users == 0
    assert point(overview, day(3)).active_users == 1
    assert overview.current.active_users == 3
    assert overview.current.avg_daily_active == round(3 / 7, 1)


async def test_a_month_counts_people_not_days(db_session: AsyncSession, teacher: User) -> None:
    regular = await make_user(db_session)
    await signed_in_at(db_session, regular, at(date(2031, 6, 2)))
    await signed_in_at(db_session, regular, at(date(2031, 6, 9)))
    await signed_in_at(db_session, regular, at(date(2031, 6, 14)))

    overview = await platform_stats.overview(db_session, "12m", now=NOW)

    assert point(overview, date(2031, 6, 1)).active_users == 1
    assert overview.current.active_users == 1
    # Three person-days over the 350 days from 1 July 2030 to today; the rest
    # of June is still ahead and does not dilute the average.
    days_so_far = (TODAY - date(2030, 7, 1)).days + 1
    assert days_so_far == 350
    assert overview.current.avg_daily_active == round(3 / days_so_far, 1)


async def test_sign_ups_are_counted_on_the_day_the_account_was_made(
    db_session: AsyncSession,
) -> None:
    newcomer = await make_user(db_session)
    newcomer.created_at = at(day(2))
    await db_session.flush()

    overview = await platform_stats.overview(db_session, "7d", now=NOW)

    assert point(overview, day(2)).new_users == 1
    assert overview.current.new_users == 1


# --- Hot courses -----------------------------------------------------------


async def test_hot_courses_are_the_ones_people_joined_most_in_the_window(
    db_session: AsyncSession, teacher: User
) -> None:
    quiet = await make_course(db_session, teacher, title="Ít người")
    popular = await make_course(db_session, teacher, title="Đông người")
    selling = await make_course(db_session, teacher, title="Đông người và bán chạy")
    stale = await make_course(db_session, teacher, title="Chỉ đông hồi trước")

    learners = [await make_user(db_session) for _ in range(4)]
    for learner in learners[:3]:
        await enrol(db_session, learner, popular, at(day(2)))
        await enrol(db_session, learner, selling, at(day(3)))
    await enrol(db_session, learners[3], quiet, at(day(1)))
    for learner in learners:
        await enrol(db_session, learner, stale, at(day(40)))
    await sell(db_session, learners[0], [(selling, "199000", "0")], paid_at=at(day(3)))

    items, total = await platform_stats.hot_courses(
        db_session, "30d", page=1, page_size=10, now=NOW
    )

    assert total == 3
    assert [item.course.title for item in items] == [
        "Đông người và bán chạy",
        "Đông người",
        "Ít người",
    ]
    assert items[0].new_enrollments == 3
    assert items[0].sales == 1
    assert items[0].revenue == Decimal("199000.00")
    assert items[1].revenue == Decimal("0.00")
