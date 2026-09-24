"""The instructor's dashboard: revenue, new students, and who finishes.

The numbers are only worth showing if each one means exactly one thing, so the
tests pin those meanings down:

* **revenue** is what buyers actually paid for *this instructor's* courses --
  net of the coupon's share on that line, never of another instructor's line
  in the same order, and only once the gateway has said the money arrived;
* a **day** is a day in Vietnam, so a sale at ten past midnight belongs to the
  new day even though it is still yesterday in UTC;
* a **new student** is somebody whose first course with this instructor began
  in the window -- two courses on the same afternoon are one new student;
* **completion** is the share of enrolments that finished, and **progress**
  the share of lessons done across every enrolment.

Every sale and enrolment is written straight into the tables with its time
spelled out, because the thing under test is how time is cut into buckets --
going through checkout would stamp everything "now".
"""

import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonProgress,
    Order,
    OrderItem,
    User,
)
from app.services.vnpay import VIETNAM
from tests.api.test_commerce import make_course, make_user, sign_in

OVERVIEW = "/api/v1/instructor/stats/overview"
COURSES = "/api/v1/instructor/stats/courses"


def today() -> date:
    return datetime.now(VIETNAM).date()


def at(day: date, hour: int = 12, minute: int = 0) -> datetime:
    """A moment on a Vietnamese calendar day."""
    return datetime.combine(day, time(hour, minute), VIETNAM)


def first_of_month(day: date, months_back: int = 0) -> date:
    month = day.year * 12 + day.month - 1 - months_back
    return date(month // 12, month % 12 + 1, 1)


async def sell(
    session: AsyncSession,
    buyer: User,
    lines: list[tuple[Course, str, str]],
    *,
    paid_at: datetime | None,
    status: str = "paid",
) -> Order:
    """An order of (course, unit price, line discount), in the given state."""
    subtotal = sum((Decimal(price) for _, price, _ in lines), Decimal(0))
    discount = sum((Decimal(off) for _, _, off in lines), Decimal(0))
    order = Order(
        user_id=buyer.id,
        code=f"DP{secrets.token_hex(6).upper()}",
        subtotal=subtotal,
        discount=discount,
        total=subtotal - discount,
        status=status,
        paid_at=paid_at if status == "paid" else None,
        provider_txn_id=secrets.token_hex(8) if status == "paid" else None,
    )
    session.add(order)
    await session.flush()
    session.add_all(
        OrderItem(
            order_id=order.id,
            course_id=course.id,
            unit_price=Decimal(price),
            discount=Decimal(off),
        )
        for course, price, off in lines
    )
    await session.flush()
    return order


async def enrol(
    session: AsyncSession,
    user: User,
    course: Course,
    *,
    when: datetime,
    completed: bool = False,
    source: str = "free",
) -> Enrollment:
    enrollment = Enrollment(
        user_id=user.id,
        course_id=course.id,
        source=source,
        created_at=when,
        completed_at=when if completed else None,
    )
    session.add(enrollment)
    await session.flush()
    return enrollment


async def add_lessons(session: AsyncSession, course: Course, count: int) -> list[Lesson]:
    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()
    lessons = [
        Lesson(section_id=section.id, title=f"Bài {i + 1}", type="article", position=i)
        for i in range(count)
    ]
    session.add_all(lessons)
    await session.flush()
    return lessons


async def finish(session: AsyncSession, enrollment: Enrollment, lessons: list[Lesson]) -> None:
    session.add_all(
        LessonProgress(
            enrollment_id=enrollment.id,
            lesson_id=lesson.id,
            completed_at=enrollment.created_at,
        )
        for lesson in lessons
    )
    await session.flush()


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def buyer(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


async def overview(client: AsyncClient, headers: dict[str, str], period: str = "30d") -> dict:
    response = await client.get(OVERVIEW, params={"period": period}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def course_rows(client: AsyncClient, headers: dict[str, str], **params) -> dict:
    response = await client.get(COURSES, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def point(body: dict, day: date) -> dict:
    return next(p for p in body["series"] if p["bucket"] == day.isoformat())


# --- Who may ask -----------------------------------------------------------


@pytest.mark.parametrize("path", [OVERVIEW, COURSES])
async def test_a_signed_out_visitor_is_told_to_sign_in(api_client: AsyncClient, path: str) -> None:
    response = await api_client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize("path", [OVERVIEW, COURSES])
async def test_a_student_has_no_dashboard(
    api_client: AsyncClient, buyer: User, path: str
) -> None:
    response = await api_client.get(path, headers=await sign_in(api_client, buyer))

    assert response.status_code == 403


async def test_a_period_that_is_not_on_the_menu_is_refused(
    api_client: AsyncClient, owner: User
) -> None:
    response = await api_client.get(
        OVERVIEW, params={"period": "45d"}, headers=await sign_in(api_client, owner)
    )

    assert response.status_code == 422


# --- Revenue ----------------------------------------------------------------


async def test_revenue_is_what_buyers_paid_for_my_courses(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    """One order, two instructors, a coupon that covered only my course: my
    revenue is my line net of its share, and none of the other line."""
    other = await make_user(db_session, "instructor")
    mine = await make_course(db_session, owner, price="400000")
    theirs = await make_course(db_session, other, price="300000")
    await sell(
        db_session,
        buyer,
        [(mine, "400000", "120000"), (theirs, "300000", "0")],
        paid_at=at(today() - timedelta(days=1)),
    )

    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"]["revenue"] == "280000.00"
    assert body["current"]["sales"] == 1
    assert body["revenue_all_time"] == "280000.00"


async def test_an_order_nobody_has_paid_for_is_not_revenue(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    course = await make_course(db_session, owner, price="400000")
    await sell(db_session, buyer, [(course, "400000", "0")], paid_at=None, status="pending")
    await sell(db_session, buyer, [(course, "400000", "0")], paid_at=None, status="failed")

    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"]["revenue"] == "0.00"
    assert body["current"]["sales"] == 0


async def test_a_sale_just_after_midnight_belongs_to_the_new_day_in_vietnam(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    """00:10 in Hà Nội is 17:10 the previous day in UTC. Bucketing in UTC
    would put tonight's first sale on yesterday's bar."""
    course = await make_course(db_session, owner, price="199000")
    day = today() - timedelta(days=2)
    await sell(db_session, buyer, [(course, "199000", "0")], paid_at=at(day, 0, 10))

    body = await overview(api_client, await sign_in(api_client, owner), "7d")

    assert point(body, day)["revenue"] == "199000.00"
    assert point(body, day - timedelta(days=1))["revenue"] == "0.00"


async def test_every_day_of_the_period_has_a_point_even_an_empty_one(
    api_client: AsyncClient, owner: User
) -> None:
    body = await overview(api_client, await sign_in(api_client, owner), "7d")

    assert body["granularity"] == "day"
    assert [p["bucket"] for p in body["series"]] == [
        (today() - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)
    ]
    assert all(p["revenue"] == "0.00" and p["sales"] == 0 for p in body["series"])
    assert body["start"] == (today() - timedelta(days=6)).isoformat()
    assert body["end"] == today().isoformat()


async def test_a_year_is_counted_in_months(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    course = await make_course(db_session, owner, price="199000")
    await sell(
        db_session, buyer, [(course, "199000", "0")], paid_at=at(first_of_month(today(), 3))
    )

    body = await overview(api_client, await sign_in(api_client, owner), "12m")

    assert body["granularity"] == "month"
    assert [p["bucket"] for p in body["series"]] == [
        first_of_month(today(), back).isoformat() for back in range(11, -1, -1)
    ]
    assert point(body, first_of_month(today(), 3))["revenue"] == "199000.00"


async def test_the_previous_period_is_the_one_just_before(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    """What "so với kỳ trước" compares against: the seven days before the
    seven on screen, not the same week last year."""
    course = await make_course(db_session, owner, price="199000")
    await sell(
        db_session, buyer, [(course, "199000", "0")], paid_at=at(today() - timedelta(days=9))
    )
    await sell(
        db_session, buyer, [(course, "199000", "0")], paid_at=at(today() - timedelta(days=20))
    )

    body = await overview(api_client, await sign_in(api_client, owner), "7d")

    assert body["current"]["revenue"] == "0.00"
    assert body["previous"]["revenue"] == "199000.00"
    assert body["revenue_all_time"] == "398000.00"


# --- Students ---------------------------------------------------------------


async def test_a_student_new_to_me_is_counted_once(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Two of my courses on the same afternoon: two enrolments, one new
    student. Somebody who has been with me since last quarter and starts
    another course today is an enrolment, not a new student."""
    first = await make_course(db_session, owner)
    second = await make_course(db_session, owner)
    newcomer = await make_user(db_session, "student")
    regular = await make_user(db_session, "student")
    yesterday = today() - timedelta(days=1)
    await enrol(db_session, newcomer, first, when=at(yesterday, 14))
    await enrol(db_session, newcomer, second, when=at(yesterday, 15))
    await enrol(db_session, regular, first, when=at(today() - timedelta(days=90)))
    await enrol(db_session, regular, second, when=at(yesterday))

    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"]["enrollments"] == 3
    assert body["current"]["new_students"] == 1
    assert point(body, yesterday)["new_students"] == 1
    assert body["students_total"] == 2


async def test_somebody_elses_students_are_not_mine(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    other = await make_user(db_session, "instructor")
    theirs = await make_course(db_session, other)
    await enrol(db_session, buyer, theirs, when=at(today()))

    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"]["enrollments"] == 0
    assert body["students_total"] == 0
    assert body["completion_rate"] is None


# --- Per course -------------------------------------------------------------


async def test_completion_and_progress_per_course(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Four students, two lessons: one finished, one halfway, two not started.
    One in four finished (0.25); three lessons done of eight (0.375)."""
    course = await make_course(db_session, owner)
    lessons = await add_lessons(db_session, course, 2)
    when = at(today() - timedelta(days=3))
    done = await enrol(
        db_session, await make_user(db_session), course, when=when, completed=True
    )
    await finish(db_session, done, lessons)
    halfway = await enrol(db_session, await make_user(db_session), course, when=when)
    await finish(db_session, halfway, lessons[:1])
    for _ in range(2):
        await enrol(db_session, await make_user(db_session), course, when=when)

    body = await course_rows(api_client, await sign_in(api_client, owner))

    [row] = body["items"]
    assert row["course"]["id"] == str(course.id)
    assert row["students"] == 4
    assert row["new_enrollments"] == 4
    assert row["completed"] == 1
    assert row["lessons_count"] == 2
    assert row["completion_rate"] == 0.25
    assert row["avg_progress"] == 0.375


async def test_a_finished_enrolment_counts_as_every_lesson_done(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """`completed_at` is the authority on "finished". A course that grew a
    lesson after somebody finished it does not make them unfinished, and on
    one row the average progress can never read lower than the share who
    completed -- 50 % finished beside 25 % progress is a contradiction."""
    course = await make_course(db_session, owner)
    lessons = await add_lessons(db_session, course, 2)
    when = at(today() - timedelta(days=3))
    # Finished, but with progress on only one of the two lessons now there.
    finished = await enrol(
        db_session, await make_user(db_session), course, when=when, completed=True
    )
    await finish(db_session, finished, lessons[:1])
    halfway = await enrol(db_session, await make_user(db_session), course, when=when)
    await finish(db_session, halfway, lessons[:1])

    body = await course_rows(api_client, await sign_in(api_client, owner))

    [row] = body["items"]
    assert row["completion_rate"] == 0.5
    assert row["avg_progress"] == 0.75


async def test_a_course_nobody_has_joined_has_no_rates_rather_than_zero(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """0% would say nobody finishes. With nobody enrolled there is no answer."""
    await make_course(db_session, owner)

    body = await course_rows(api_client, await sign_in(api_client, owner))

    [row] = body["items"]
    assert row["students"] == 0
    assert row["completion_rate"] is None
    assert row["avg_progress"] is None


async def test_each_course_carries_its_own_revenue(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    selling = await make_course(db_session, owner, price="400000", title="Bán chạy")
    quiet = await make_course(db_session, owner, price="199000", title="Chưa bán")
    await sell(
        db_session, buyer, [(selling, "400000", "100000")], paid_at=at(today() - timedelta(days=1))
    )
    await sell(
        db_session, buyer, [(selling, "400000", "0")], paid_at=at(today() - timedelta(days=60))
    )

    body = await course_rows(api_client, await sign_in(api_client, owner), period="30d")

    # Best seller of the period first.
    assert [row["course"]["id"] for row in body["items"]] == [str(selling.id), str(quiet.id)]
    top = body["items"][0]
    assert top["revenue"] == "300000.00"
    assert top["sales"] == 1
    assert top["revenue_all_time"] == "700000.00"


async def test_only_my_courses_are_listed_and_they_are_paged(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    for _ in range(3):
        await make_course(db_session, owner)
    await make_course(db_session, await make_user(db_session, "instructor"))

    body = await course_rows(api_client, await sign_in(api_client, owner), page_size=2)

    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page_size"] == 2


async def test_a_removed_course_stays_while_it_still_has_students(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    """Soft delete keeps a course for the people who bought it, so it keeps
    its row here for as long as there is somebody to count. One that nobody
    ever joined is simply gone."""
    kept = await make_course(db_session, owner)
    gone = await make_course(db_session, owner)
    await enrol(db_session, buyer, kept, when=at(today()))
    for course in (kept, gone):
        course.deleted_at = datetime.now(VIETNAM)
    await db_session.flush()

    body = await course_rows(api_client, await sign_in(api_client, owner))

    assert [row["course"]["id"] for row in body["items"]] == [str(kept.id)]
    assert body["items"][0]["course"]["is_deleted"] is True


async def test_overall_completion_is_over_every_enrolment(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    first = await make_course(db_session, owner)
    second = await make_course(db_session, owner)
    when = at(today() - timedelta(days=100))
    await enrol(db_session, await make_user(db_session), first, when=when, completed=True)
    await enrol(db_session, await make_user(db_session), second, when=when)
    await enrol(db_session, await make_user(db_session), second, when=when)
    await enrol(db_session, await make_user(db_session), second, when=when)

    body = await overview(api_client, await sign_in(api_client, owner))

    # All-time, not the period: nobody joined in the last 30 days, but a
    # quarter of everybody who ever joined has finished.
    assert body["current"]["enrollments"] == 0
    assert body["completion_rate"] == 0.25
    assert body["courses_count"] == 2


async def test_an_instructor_with_nothing_yet_gets_an_empty_dashboard(
    api_client: AsyncClient, owner: User
) -> None:
    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"] == {
        "revenue": "0.00",
        "sales": 0,
        "enrollments": 0,
        "new_students": 0,
    }
    assert body["courses_count"] == 0
    assert len(body["series"]) == 30
