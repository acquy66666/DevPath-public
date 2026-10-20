"""The admin's dashboard: the whole platform, and what each number means.

The calendar is the shared one (`services/stats_calendar.py`):
days and months on the Vietnamese calendar, "7 ngày" is today and the six
days before it, "12 tháng" is whole months with this one filling up, and every
figure is compared with the window of the same length just before.

**Revenue** is what buyers paid the platform: `orders.total` of orders the
gateway confirmed (`status = 'paid'`), dated by `paid_at`. The order total is
already net of the coupon, so summing it is exact; the finance pages split it
per line only because an order can hold several instructors' courses. Gross,
before instructors' shares -- those, and what the platform
keeps, are on the finance pages (`services/finance.py`).

**An active user** on a day is somebody who left a trace on that day, in any of
the append-only records the platform already keeps:

* `refresh_tokens.created_at` -- every sign-in, and every time an open tab
  renews its session (an access token lives 15 minutes, and a page load always
  renews). This is the trace of someone who only browsed.
* learning: `lesson_progress` (a touched lesson), `xp_events`, `quiz_attempts`
  started, code `submissions`, questions and answers to the AI assistant
  (`chat_messages` of role `user`), Q&A threads and replies, notes;
* buying and joining: `orders` created, `enrollments`.

No table was added for this: a `user_activity_days` row per request would be a
write on every page view, to store what these tables already say. The price is
that a row updated in place keeps only its last day -- a lesson revisited
three days running counts on the third -- which undercounts a little and never
overcounts. **DAU** is that count per day; a month bar is the distinct users of
the month, not a sum of days.

**Hot courses** are the ones with the most new enrolments in the window, then
the most revenue from it, then the best rating.

Nothing here is cached or stored; every figure is an aggregate.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChatMessage,
    ChatSession,
    Course,
    Enrollment,
    LessonProgress,
    Note,
    Order,
    OrderItem,
    QaReply,
    QaThread,
    QuizAttempt,
    RefreshToken,
    Submission,
    User,
    XpEvent,
)
from app.services.stats_calendar import (
    ZERO,
    Window,
    bucket_start,
    money,
    vietnam_today,
    windows,
)

#: What buyers paid for one sold line -- the per-course half of revenue.
NET = OrderItem.unit_price - OrderItem.discount


# --- Who was active --------------------------------------------------------


def _traces(start: datetime, stop: datetime) -> Select:
    """(user_id, at) for every recorded action in [start, stop)."""
    sources = [
        (RefreshToken.user_id, RefreshToken.created_at),
        (XpEvent.user_id, XpEvent.created_at),
        (QuizAttempt.user_id, QuizAttempt.started_at),
        (Submission.user_id, Submission.created_at),
        (QaThread.user_id, QaThread.created_at),
        (QaReply.user_id, QaReply.created_at),
        (Note.user_id, Note.created_at),
        (Order.user_id, Order.created_at),
        (Enrollment.user_id, Enrollment.created_at),
    ]
    parts = [
        select(user_id.label("user_id"), at.label("at")).where(at >= start, at < stop)
        for user_id, at in sources
    ]
    # Two rows that carry no user themselves: progress hangs off an enrolment,
    # a question to the AI assistant off its chat session.
    parts.append(
        select(Enrollment.user_id.label("user_id"), LessonProgress.updated_at.label("at"))
        .join(Enrollment, Enrollment.id == LessonProgress.enrollment_id)
        .where(LessonProgress.updated_at >= start, LessonProgress.updated_at < stop)
    )
    parts.append(
        select(ChatSession.user_id.label("user_id"), ChatMessage.created_at.label("at"))
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(
            ChatMessage.role == "user",
            ChatMessage.created_at >= start,
            ChatMessage.created_at < stop,
        )
    )
    return union_all(*parts)


async def _active_per_bucket(session: AsyncSession, window: Window) -> dict[date, int]:
    traces = _traces(*window.bounds()).subquery()
    bucket = bucket_start(traces.c.at, window.granularity).label("bucket")
    rows = await session.execute(
        select(bucket, func.count(func.distinct(traces.c.user_id))).group_by(bucket)
    )
    return {day: count for day, count in rows}


async def _active_per_day(session: AsyncSession, window: Window) -> dict[date, int]:
    traces = _traces(*window.bounds()).subquery()
    day = bucket_start(traces.c.at, "day").label("day")
    rows = await session.execute(
        select(day, func.count(func.distinct(traces.c.user_id))).group_by(day)
    )
    return {bucket: count for bucket, count in rows}


async def _active_in(session: AsyncSession, window: Window) -> int:
    traces = _traces(*window.bounds()).subquery()
    return await session.scalar(select(func.count(func.distinct(traces.c.user_id)))) or 0


# --- Overview --------------------------------------------------------------


@dataclass(slots=True)
class Totals:
    revenue: Decimal = ZERO
    orders: int = 0
    enrollments: int = 0
    new_users: int = 0
    #: Distinct users active anywhere in the window.
    active_users: int = 0
    #: Mean of the daily counts over the window's days (so far).
    avg_daily_active: float = 0.0


@dataclass(slots=True)
class Point:
    bucket: date
    revenue: Decimal = ZERO
    orders: int = 0
    enrollments: int = 0
    new_users: int = 0
    active_users: int = 0


@dataclass(frozen=True, slots=True)
class Overview:
    period: str
    granularity: str
    start: date
    end: date
    current: Totals
    previous: Totals
    series: list[Point]
    active_today: int
    revenue_all_time: Decimal
    users_total: int
    courses_published: int
    enrollments_total: int


async def _series(session: AsyncSession, window: Window) -> list[Point]:
    start, stop = window.bounds()
    points = {bucket: Point(bucket=bucket) for bucket in window.buckets()}
    granularity = window.granularity

    paid = bucket_start(Order.paid_at, granularity).label("bucket")
    for bucket, revenue, orders in await session.execute(
        select(paid, func.sum(Order.total), func.count())
        .where(Order.status == "paid", Order.paid_at >= start, Order.paid_at < stop)
        .group_by(paid)
    ):
        points[bucket].revenue = money(revenue)
        points[bucket].orders = orders

    joined = bucket_start(Enrollment.created_at, granularity).label("bucket")
    for bucket, count in await session.execute(
        select(joined, func.count())
        .where(Enrollment.created_at >= start, Enrollment.created_at < stop)
        .group_by(joined)
    ):
        points[bucket].enrollments = count

    signed_up = bucket_start(User.created_at, granularity).label("bucket")
    for bucket, count in await session.execute(
        select(signed_up, func.count())
        .where(User.created_at >= start, User.created_at < stop)
        .group_by(signed_up)
    ):
        points[bucket].new_users = count

    for bucket, count in (await _active_per_bucket(session, window)).items():
        points[bucket].active_users = count

    return list(points.values())


async def _totals(
    session: AsyncSession, window: Window, series: list[Point], today: date
) -> Totals:
    # Days that have happened: a month window runs to the end of the month,
    # and the days still ahead would drag the average down for nothing.
    days = max(1, (min(window.stop, today + timedelta(days=1)) - window.start).days)
    daily = await _active_per_day(session, window)
    return Totals(
        revenue=sum((point.revenue for point in series), ZERO),
        orders=sum(point.orders for point in series),
        enrollments=sum(point.enrollments for point in series),
        new_users=sum(point.new_users for point in series),
        active_users=await _active_in(session, window),
        avg_daily_active=round(sum(daily.values()) / days, 1),
    )


async def overview(session: AsyncSession, period: str, *, now: datetime | None = None) -> Overview:
    today = vietnam_today(now)
    current, previous = windows(period, today)
    series = await _series(session, current)
    previous_series = await _series(session, previous)

    revenue_all_time = await session.scalar(
        select(func.sum(Order.total)).where(Order.status == "paid")
    )
    today_window = Window(today, today + timedelta(days=1), "day")

    return Overview(
        period=period,
        granularity=current.granularity,
        start=current.start,
        end=min(current.stop - timedelta(days=1), today),
        current=await _totals(session, current, series, today),
        previous=await _totals(session, previous, previous_series, today),
        series=series,
        active_today=await _active_in(session, today_window),
        revenue_all_time=money(revenue_all_time),
        users_total=await session.scalar(select(func.count()).select_from(User)) or 0,
        courses_published=await session.scalar(
            select(func.count())
            .select_from(Course)
            .where(Course.status == "published", Course.deleted_at.is_(None))
        )
        or 0,
        enrollments_total=await session.scalar(select(func.count()).select_from(Enrollment))
        or 0,
    )


# --- Hot courses -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HotCourse:
    course: Course
    instructor: User
    new_enrollments: int
    sales: int
    revenue: Decimal


async def hot_courses(
    session: AsyncSession,
    period: str,
    *,
    page: int,
    page_size: int,
    now: datetime | None = None,
) -> tuple[list[HotCourse], int]:
    """Courses that gained students in the window, most first.

    Only courses with at least one new enrolment in the window are listed --
    "hot" over a window where nothing happened would be a list of zeros.
    """
    window, _ = windows(period, vietnam_today(now))
    start, stop = window.bounds()

    joined = (
        select(Enrollment.course_id, func.count().label("new_enrollments"))
        .where(Enrollment.created_at >= start, Enrollment.created_at < stop)
        .group_by(Enrollment.course_id)
        .subquery()
    )
    sold = (
        select(
            OrderItem.course_id,
            func.count().label("sales"),
            func.sum(NET).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status == "paid", Order.paid_at >= start, Order.paid_at < stop)
        .group_by(OrderItem.course_id)
        .subquery()
    )
    listing = (
        select(
            Course,
            User,
            joined.c.new_enrollments,
            func.coalesce(sold.c.sales, 0),
            func.coalesce(sold.c.revenue, 0),
        )
        .join(joined, joined.c.course_id == Course.id)
        .join(User, User.id == Course.instructor_id)
        .outerjoin(sold, sold.c.course_id == Course.id)
    )

    total = await session.scalar(select(func.count()).select_from(joined))
    rows = await session.execute(
        listing.order_by(
            joined.c.new_enrollments.desc(),
            func.coalesce(sold.c.revenue, 0).desc(),
            Course.rating_avg.desc(),
            Course.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [
        HotCourse(
            course=course,
            instructor=instructor,
            new_enrollments=new_enrollments,
            sales=sales,
            revenue=money(revenue),
        )
        for course, instructor, new_enrollments, sales, revenue in rows
    ], total or 0
