"""The numbers on an instructor's dashboard, and what each one means.

**Revenue** is what buyers actually paid for this instructor's courses: each
sold line's `unit_price` minus its own `discount`, from orders the gateway has
confirmed (`status = 'paid'`), dated by `paid_at`. Not the order's total -- an
order can hold several instructors' courses -- and not `unit_price` alone, or a
coupon would be revenue nobody received. It is the gross the buyer paid: a
platform fee would come off it, but revenue sharing is future work in the
thesis outline, so there is nothing yet to take off.

**A day is a day in Vietnam.** Buckets are cut on the Vietnamese calendar
(UTC+7, the same clock the VNPay integration uses), so a sale at 00:10 in Hà
Nội is on today's bar even though it is 17:10 yesterday in UTC. The windows are
calendar-aligned too: "7 ngày" is today and the six days before it.

**A new student** is somebody whose *first* enrolment in any of this
instructor's courses began in the window. Two courses on one afternoon are two
enrolments and one new student; a regular starting another course is an
enrolment and not a new student.

**Completion** is finished enrolments over enrolments; **progress** is lessons
done over lessons there are, across every enrolment -- with a finished
enrolment counted as every lesson done. `completed_at` is the authority on
finishing: a course that grows a lesson afterwards does not un-finish anybody,
and one row can never show 50 % completed beside 25 % progress. Both are
all-time and both are null -- not zero -- when there is nobody to measure: 0%
would say nobody finishes.

Nothing here is cached or stored. Every figure is an aggregate over rows the
rest of the system already keeps, for one instructor's handful of courses, and
two indexes added with this module (`ix_order_items_course_id`,
`ix_enrollments_course_created`) are what keep the per-course reads from
scanning the tables.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import ColumnElement, Date, and_, case, cast, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonProgress,
    Order,
    OrderItem,
)
from app.services.vnpay import VIETNAM

#: What the dashboard can be asked for: a length, and the bucket it is cut in.
PERIODS: dict[str, tuple[int, str]] = {
    "7d": (7, "day"),
    "30d": (30, "day"),
    "90d": (90, "day"),
    "12m": (12, "month"),
}
GRANULARITIES = ("day", "month")

#: The clock `VIETNAM` is, by name. Not '+07:00': Postgres reads an offset
#: string in AT TIME ZONE as a POSIX zone, where positive means *west* of
#: Greenwich, and every bucket would land fourteen hours off.
TIMEZONE = "Asia/Ho_Chi_Minh"

ZERO = Decimal("0.00")
RATE_PLACES = 4


# --- Windows ---------------------------------------------------------------


def _add_months(first_of_month: date, months: int) -> date:
    index = first_of_month.year * 12 + first_of_month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


@dataclass(frozen=True, slots=True)
class Window:
    """A stretch of Vietnamese calendar: `start` inclusive, `stop` exclusive."""

    start: date
    stop: date
    granularity: str

    def bounds(self) -> tuple[datetime, datetime]:
        return (
            datetime.combine(self.start, time(), VIETNAM),
            datetime.combine(self.stop, time(), VIETNAM),
        )

    def buckets(self) -> list[date]:
        if self.granularity == "day":
            return [
                self.start + timedelta(days=offset)
                for offset in range((self.stop - self.start).days)
            ]
        months: list[date] = []
        month = self.start
        while month < self.stop:
            months.append(month)
            month = _add_months(month, 1)
        return months


def windows(period: str, today: date) -> tuple[Window, Window]:
    """The window a period names, ending today, and the one just before it."""
    length, granularity = PERIODS[period]

    if granularity == "day":
        stop = today + timedelta(days=1)
        start = stop - timedelta(days=length)
        return (
            Window(start, stop, granularity),
            Window(start - timedelta(days=length), start, granularity),
        )

    # Whole months, this one included, so every bar is a full calendar month
    # and the last one fills up as the month goes on.
    stop = _add_months(today.replace(day=1), 1)
    start = _add_months(stop, -length)
    return (
        Window(start, stop, granularity),
        Window(_add_months(start, -length), start, granularity),
    )


def _today(now: datetime | None) -> date:
    return (now or datetime.now(UTC)).astimezone(VIETNAM).date()


def _bucket(column: ColumnElement[datetime], granularity: str) -> ColumnElement[date]:
    """The first day of the bucket `column` falls in, on the Vietnamese calendar.

    Both arguments are rendered as literals rather than bound: the expression
    appears in SELECT and again in GROUP BY, and Postgres only recognises the
    two as one expression when they are the same text -- two bind parameters
    are two expressions to it, whatever they hold.
    """
    if granularity not in GRANULARITIES:
        raise ValueError(granularity)
    local = func.timezone(literal_column(f"'{TIMEZONE}'"), column)
    return cast(func.date_trunc(literal_column(f"'{granularity}'"), local), Date)


def _rate(part: int, whole: int) -> float | None:
    return None if whole == 0 else round(part / whole, RATE_PLACES)


def _money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(ZERO)


#: What a buyer paid for one sold line.
NET = OrderItem.unit_price - OrderItem.discount


# --- Overview --------------------------------------------------------------


@dataclass(slots=True)
class Totals:
    revenue: Decimal = ZERO
    sales: int = 0
    enrollments: int = 0
    new_students: int = 0


@dataclass(slots=True, kw_only=True)
class Point(Totals):
    bucket: date


@dataclass(frozen=True, slots=True)
class Overview:
    period: str
    granularity: str
    start: date
    end: date
    current: Totals
    previous: Totals
    series: list[Point]
    revenue_all_time: Decimal
    students_total: int
    completion_rate: float | None
    courses_count: int


async def _series(
    session: AsyncSession, instructor_id: uuid.UUID, window: Window
) -> list[Point]:
    """One point per bucket of the window, empty ones included."""
    start, stop = window.bounds()
    mine = Course.instructor_id == instructor_id
    points = {bucket: Point(bucket=bucket) for bucket in window.buckets()}

    sold = _bucket(Order.paid_at, window.granularity).label("bucket")
    for bucket, revenue, sales in await session.execute(
        select(sold, func.sum(NET), func.count())
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Course, Course.id == OrderItem.course_id)
        .where(mine, Order.status == "paid", Order.paid_at >= start, Order.paid_at < stop)
        .group_by(sold)
    ):
        points[bucket].revenue = _money(revenue)
        points[bucket].sales = sales

    joined = _bucket(Enrollment.created_at, window.granularity).label("bucket")
    for bucket, count in await session.execute(
        select(joined, func.count())
        .select_from(Enrollment)
        .join(Course, Course.id == Enrollment.course_id)
        .where(mine, Enrollment.created_at >= start, Enrollment.created_at < stop)
        .group_by(joined)
    ):
        points[bucket].enrollments = count

    # Everybody's first enrolment with this instructor, then only those that
    # fall in the window -- filtering first would make last quarter's regular
    # look new the moment they start something else.
    first = (
        select(Enrollment.user_id, func.min(Enrollment.created_at).label("first_at"))
        .join(Course, Course.id == Enrollment.course_id)
        .where(mine)
        .group_by(Enrollment.user_id)
        .subquery()
    )
    arrived = _bucket(first.c.first_at, window.granularity).label("bucket")
    for bucket, count in await session.execute(
        select(arrived, func.count())
        .where(first.c.first_at >= start, first.c.first_at < stop)
        .group_by(arrived)
    ):
        points[bucket].new_students = count

    return list(points.values())


def _sum(points: list[Point]) -> Totals:
    return Totals(
        revenue=sum((point.revenue for point in points), ZERO),
        sales=sum(point.sales for point in points),
        enrollments=sum(point.enrollments for point in points),
        new_students=sum(point.new_students for point in points),
    )


async def overview(
    session: AsyncSession,
    instructor_id: uuid.UUID,
    period: str,
    *,
    now: datetime | None = None,
) -> Overview:
    """Totals for the period and the one before it, the series behind the
    chart, and the all-time figures that describe the instructor."""
    today = _today(now)
    current, previous = windows(period, today)
    series = await _series(session, instructor_id, current)
    mine = Course.instructor_id == instructor_id

    revenue_all_time = await session.scalar(
        select(func.sum(NET))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Course, Course.id == OrderItem.course_id)
        .where(mine, Order.status == "paid")
    )
    enrolments, completed, students = (
        await session.execute(
            select(
                func.count(),
                func.count(Enrollment.completed_at),
                func.count(func.distinct(Enrollment.user_id)),
            )
            .select_from(Enrollment)
            .join(Course, Course.id == Enrollment.course_id)
            .where(mine)
        )
    ).one()
    courses_count = await session.scalar(
        select(func.count()).select_from(Course).where(mine, Course.deleted_at.is_(None))
    )

    return Overview(
        period=period,
        granularity=current.granularity,
        start=current.start,
        # A month-long bar runs to the end of the month; the range printed
        # above the chart stops at today.
        end=min(current.stop - timedelta(days=1), today),
        current=_sum(series),
        previous=_sum(await _series(session, instructor_id, previous)),
        series=series,
        revenue_all_time=_money(revenue_all_time),
        students_total=students,
        completion_rate=_rate(completed, enrolments),
        courses_count=courses_count or 0,
    )


# --- Per course ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CourseStats:
    course: Course
    students: int
    completed: int
    lessons_count: int
    completion_rate: float | None
    avg_progress: float | None
    new_enrollments: int
    sales: int
    revenue: Decimal
    revenue_all_time: Decimal


async def course_stats(
    session: AsyncSession,
    instructor_id: uuid.UUID,
    period: str,
    *,
    page: int,
    page_size: int,
    now: datetime | None = None,
) -> tuple[list[CourseStats], int]:
    """One row per course, best seller of the period first.

    A course that was taken down stays listed while anybody is still enrolled
    in it or it has ever sold -- soft delete exists so that those people keep
    their course, and its instructor keeps seeing how they get on. One that
    nobody ever joined is gone.

    Each aggregate is a subquery limited to this instructor's courses, joined
    onto the course list, so one statement answers the page and the sort runs
    on the real numbers rather than on a page-sized sample of them.
    """
    window, _ = windows(period, _today(now))
    start, stop = window.bounds()
    mine = select(Course.id).where(Course.instructor_id == instructor_id)

    joined_in_window = and_(Enrollment.created_at >= start, Enrollment.created_at < stop)
    enrolled = (
        select(
            Enrollment.course_id,
            func.count().label("students"),
            func.count(Enrollment.completed_at).label("completed"),
            func.count().filter(joined_in_window).label("new_enrollments"),
        )
        .where(Enrollment.course_id.in_(mine))
        .group_by(Enrollment.course_id)
        .subquery()
    )
    lessons = (
        select(CourseSection.course_id, func.count(Lesson.id).label("lessons"))
        .join(Lesson, Lesson.section_id == CourseSection.id)
        .where(CourseSection.course_id.in_(mine))
        .group_by(CourseSection.course_id)
        .subquery()
    )
    # Lessons done per enrolment first, then per course: a finished enrolment
    # counts as every lesson done (see `test_a_finished_enrolment_...`), and
    # nobody counts as more than all of them.
    per_enrolment = (
        select(
            Enrollment.course_id,
            Enrollment.completed_at,
            func.count(LessonProgress.id)
            .filter(LessonProgress.completed_at.is_not(None))
            .label("done"),
        )
        .outerjoin(LessonProgress, LessonProgress.enrollment_id == Enrollment.id)
        .where(Enrollment.course_id.in_(mine))
        .group_by(Enrollment.id)
        .subquery()
    )
    done = (
        select(
            per_enrolment.c.course_id,
            func.sum(
                case(
                    (per_enrolment.c.completed_at.is_not(None), lessons.c.lessons),
                    else_=func.least(per_enrolment.c.done, lessons.c.lessons),
                )
            ).label("done"),
        )
        .join(lessons, lessons.c.course_id == per_enrolment.c.course_id)
        .group_by(per_enrolment.c.course_id)
        .subquery()
    )
    paid_in_window = and_(Order.paid_at >= start, Order.paid_at < stop)
    sold = (
        select(
            OrderItem.course_id,
            func.sum(NET).label("revenue_all_time"),
            func.sum(NET).filter(paid_in_window).label("revenue"),
            func.count().filter(paid_in_window).label("sales"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.course_id.in_(mine), Order.status == "paid")
        .group_by(OrderItem.course_id)
        .subquery()
    )

    students = func.coalesce(enrolled.c.students, 0)
    revenue = func.coalesce(sold.c.revenue, 0)
    revenue_all_time = func.coalesce(sold.c.revenue_all_time, 0)

    rows = (
        select(
            Course,
            students.label("students"),
            func.coalesce(enrolled.c.completed, 0).label("completed"),
            func.coalesce(enrolled.c.new_enrollments, 0).label("new_enrollments"),
            func.coalesce(lessons.c.lessons, 0).label("lessons"),
            func.coalesce(done.c.done, 0).label("done"),
            func.coalesce(sold.c.sales, 0).label("sales"),
            revenue.label("revenue"),
            revenue_all_time.label("revenue_all_time"),
        )
        .outerjoin(enrolled, enrolled.c.course_id == Course.id)
        .outerjoin(lessons, lessons.c.course_id == Course.id)
        .outerjoin(done, done.c.course_id == Course.id)
        .outerjoin(sold, sold.c.course_id == Course.id)
        .where(
            Course.instructor_id == instructor_id,
            or_(Course.deleted_at.is_(None), students > 0, revenue_all_time > 0),
        )
    )

    total = await session.scalar(select(func.count()).select_from(rows.subquery()))
    result = await session.execute(
        rows.order_by(
            revenue.desc(), students.desc(), Course.created_at.desc(), Course.id
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = [
        CourseStats(
            course=row.Course,
            students=row.students,
            completed=row.completed,
            lessons_count=row.lessons,
            completion_rate=_rate(row.completed, row.students),
            avg_progress=_rate(row.done, row.students * row.lessons),
            new_enrollments=row.new_enrollments,
            sales=row.sales,
            revenue=_money(row.revenue),
            revenue_all_time=_money(row.revenue_all_time),
        )
        for row in result
    ]
    return items, total or 0
