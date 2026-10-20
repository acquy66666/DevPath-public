"""Money, for the admin: what came in, whose it is, and what the platform kept.

Every figure is built on one sold line (`order_items`) of a paid order:

* **list** -- `unit_price`, the price the course was sold at (GMV);
* **discount** -- the line's share of the coupon;
* **paid** -- `unit_price - discount`, what the buyer actually paid. The lines
  of an order add up to `orders.total`;
* **instructor share** -- `floor(paid x instructor_share_rate)`, the rate the
  line was frozen with when the order was paid (`orders._deliver`), rounded
  down to the đồng;
* **platform share** -- `paid - instructor share`.

So the coupon is borne by both sides in proportion -- the share is computed on
what was paid, as Udemy's "net amount" is -- and the gateway's fee comes out of
the platform's share (the profit page estimates it). Dates are `paid_at`, on
the Vietnamese calendar; buckets are hours, days, ISO weeks (Monday first),
months, quarters or years.

Nothing is cached. The calendar is `services/stats_calendar.py`.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal

from fastapi import status
from sqlalchemy import Select, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Course, InstructorTier, Order, OrderItem, User
from app.services.stats_calendar import ZERO, add_months, local, money
from app.services.vnpay import VIETNAM

FINANCE_GRANULARITIES = ("hour", "day", "week", "month", "quarter", "year")
#: The longest range each bucket size may cover -- a chart of 9 000 hourly
#: bars is not a chart. Hourly is for "what happened this week".
MAX_DAYS = {"hour": 7, "day": 366, "week": 1100, "month": 3660, "quarter": 3660, "year": 3660}

PAID = OrderItem.unit_price - OrderItem.discount
INSTRUCTOR_SHARE = func.floor(PAID * func.coalesce(OrderItem.instructor_share_rate, 0))


def share_of(paid: Decimal, share_rate: Decimal) -> Decimal:
    """`floor(paid x rate)` to the đồng -- what `INSTRUCTOR_SHARE` computes in SQL."""
    return (paid * share_rate).quantize(Decimal("1"), rounding=ROUND_DOWN).quantize(ZERO)


class RangeError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "INVALID_RANGE"


# --- Ranges and buckets ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Range:
    """`start`..`end`, both inclusive, Vietnamese calendar."""

    start: date
    end: date
    granularity: str

    def bounds(self) -> tuple[datetime, datetime]:
        return (
            datetime.combine(self.start, time(), VIETNAM),
            datetime.combine(self.end + timedelta(days=1), time(), VIETNAM),
        )

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> "Range":
        """The range of the same length just before this one."""
        return Range(
            self.start - timedelta(days=self.days),
            self.start - timedelta(days=1),
            self.granularity,
        )

    def buckets(self) -> list[datetime]:
        """The first moment of every bucket that overlaps the range, as naive
        Vietnamese wall-clock time -- the same thing `_bucket` returns."""
        first = _floor(datetime.combine(self.start, time()), self.granularity)
        stop = datetime.combine(self.end + timedelta(days=1), time())
        buckets = []
        moment = first
        while moment < stop:
            buckets.append(moment)
            moment = _next(moment, self.granularity)
        return buckets


def _floor(moment: datetime, granularity: str) -> datetime:
    if granularity == "hour":
        return moment.replace(minute=0, second=0, microsecond=0)
    day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "day":
        return day
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    if granularity == "quarter":
        return day.replace(month=(day.month - 1) // 3 * 3 + 1, day=1)
    return day.replace(month=1, day=1)


def _next(moment: datetime, granularity: str) -> datetime:
    if granularity == "hour":
        return moment + timedelta(hours=1)
    if granularity == "day":
        return moment + timedelta(days=1)
    if granularity == "week":
        return moment + timedelta(days=7)
    months = {"month": 1, "quarter": 3, "year": 12}[granularity]
    return datetime.combine(add_months(moment.date(), months), time())


def make_range(start: date, end: date, granularity: str) -> Range:
    if granularity not in FINANCE_GRANULARITIES:
        raise RangeError("Mốc thời gian không hợp lệ")
    if end < start:
        raise RangeError("Ngày kết thúc phải sau ngày bắt đầu")
    span = (end - start).days + 1
    if span > MAX_DAYS[granularity]:
        raise RangeError(
            f"Xem theo {GRANULARITY_LABELS[granularity]} chỉ cho khoảng tối đa "
            f"{MAX_DAYS[granularity]} ngày"
        )
    return Range(start, end, granularity)


GRANULARITY_LABELS = {
    "hour": "giờ",
    "day": "ngày",
    "week": "tuần",
    "month": "tháng",
    "quarter": "quý",
    "year": "năm",
}


def _bucket(column, granularity: str):
    """The first moment of the bucket `column` falls in, Vietnamese wall clock.

    Rendered as literals, not bind parameters, so SELECT and GROUP BY are the
    same expression to Postgres (see `stats_calendar.bucket_start`).
    """
    return func.date_trunc(literal_column(f"'{granularity}'"), local(column))


# --- Totals ------------------------------------------------------------------


@dataclass(slots=True)
class Money:
    orders: int = 0
    lines: int = 0
    buyers: int = 0
    list_amount: Decimal = ZERO
    discount: Decimal = ZERO
    paid: Decimal = ZERO
    instructor_share: Decimal = ZERO
    platform_share: Decimal = ZERO


@dataclass(slots=True)
class MoneyPoint(Money):
    bucket: datetime = datetime.min


def _amounts():
    return (
        func.count(func.distinct(Order.id)).label("orders"),
        func.count(OrderItem.id).label("lines"),
        func.count(func.distinct(Order.user_id)).label("buyers"),
        func.coalesce(func.sum(OrderItem.unit_price), 0).label("list_amount"),
        func.coalesce(func.sum(OrderItem.discount), 0).label("discount"),
        func.coalesce(func.sum(PAID), 0).label("paid"),
        func.coalesce(func.sum(INSTRUCTOR_SHARE), 0).label("instructor_share"),
    )


def _fill(target: Money, row) -> Money:
    target.orders = row.orders
    target.lines = row.lines
    target.buyers = row.buyers
    target.list_amount = money(row.list_amount)
    target.discount = money(row.discount)
    target.paid = money(row.paid)
    target.instructor_share = money(row.instructor_share)
    target.platform_share = money(row.paid - row.instructor_share)
    return target


def _sold(start: datetime, stop: datetime, instructor_id: uuid.UUID | None) -> Select:
    query = (
        select()
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status == "paid", Order.paid_at >= start, Order.paid_at < stop)
    )
    if instructor_id is not None:
        query = query.join(Course, Course.id == OrderItem.course_id).where(
            Course.instructor_id == instructor_id
        )
    return query


async def _totals(session: AsyncSession, span: Range, instructor_id: uuid.UUID | None) -> Money:
    row = (
        await session.execute(_sold(*span.bounds(), instructor_id).add_columns(*_amounts()))
    ).one()
    return _fill(Money(), row)


@dataclass(frozen=True, slots=True)
class RevenueReport:
    range: Range
    instructor: User | None
    totals: Money
    previous: Money
    series: list[MoneyPoint]


async def revenue(
    session: AsyncSession,
    span: Range,
    *,
    instructor_id: uuid.UUID | None = None,
) -> RevenueReport:
    """The range bucket by bucket, its totals, and the range just before it."""
    instructor = None
    if instructor_id is not None:
        instructor = await session.get(User, instructor_id)
        if instructor is None or instructor.role != "instructor":
            raise DomainError(
                "Không tìm thấy giảng viên này",
                code="INSTRUCTOR_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    points = {bucket: MoneyPoint(bucket=bucket) for bucket in span.buckets()}
    bucket = _bucket(Order.paid_at, span.granularity).label("bucket")
    for row in await session.execute(
        _sold(*span.bounds(), instructor_id).add_columns(bucket, *_amounts()).group_by(bucket)
    ):
        _fill(points[row.bucket], row)

    return RevenueReport(
        range=span,
        instructor=instructor,
        totals=await _totals(session, span, instructor_id),
        previous=await _totals(session, span.previous(), instructor_id),
        series=list(points.values()),
    )


# --- By instructor, by course ------------------------------------------------


@dataclass(slots=True)
class InstructorMoney(Money):
    instructor: User | None = None
    tier: InstructorTier | None = None
    courses_sold: int = 0
    #: This instructor's part of everything paid in the range.
    share_of_paid: float | None = None


@dataclass(slots=True)
class CourseMoney(Money):
    course: Course | None = None
    instructor: User | None = None


async def by_instructor(session: AsyncSession, span: Range) -> list[InstructorMoney]:
    """Every instructor who sold something in the range, most paid first."""
    tiers = list(await session.scalars(select(InstructorTier).order_by(InstructorTier.rank)))
    base = tiers[0]
    by_id = {tier.id: tier for tier in tiers}

    rows = await session.execute(
        _sold(*span.bounds(), None)
        .join(Course, Course.id == OrderItem.course_id)
        .join(User, User.id == Course.instructor_id)
        .add_columns(User, func.count(func.distinct(Course.id)).label("courses"), *_amounts())
        .group_by(User.id)
        .order_by(func.sum(PAID).desc(), User.full_name)
    )
    result = []
    for row in rows:
        item = _fill(InstructorMoney(), row)
        item.instructor = row.User
        item.tier = by_id.get(row.User.instructor_tier_id, base)
        item.courses_sold = row.courses
        result.append(item)
    total = sum((item.paid for item in result), ZERO)
    for item in result:
        item.share_of_paid = round(float(item.paid / total), 4) if total else None
    return result


async def by_course(
    session: AsyncSession, span: Range, *, instructor_id: uuid.UUID | None = None
) -> list[CourseMoney]:
    """Every course that sold in the range, most paid first."""
    query = _sold(*span.bounds(), None).join(Course, Course.id == OrderItem.course_id)
    if instructor_id is not None:
        query = query.where(Course.instructor_id == instructor_id)
    rows = await session.execute(
        query.join(User, User.id == Course.instructor_id)
        .add_columns(Course, User, *_amounts())
        .group_by(Course.id, User.id)
        .order_by(func.sum(PAID).desc(), Course.title)
    )
    result = []
    for row in rows:
        item = _fill(CourseMoney(), row)
        item.course = row.Course
        item.instructor = row.User
        result.append(item)
    return result


@dataclass(frozen=True, slots=True)
class SoldLine:
    order_code: str
    paid_at: datetime
    course_title: str
    instructor_name: str
    unit_price: Decimal
    discount: Decimal
    paid: Decimal
    share_rate: Decimal | None
    instructor_share: Decimal
    platform_share: Decimal
    coupon_code: str | None
    payment_provider: str


async def lines(
    session: AsyncSession, span: Range, *, instructor_id: uuid.UUID | None = None
) -> list[SoldLine]:
    """Every sold line of the range, oldest first -- the export's detail sheet."""
    query = (
        _sold(*span.bounds(), None)
        .join(Course, Course.id == OrderItem.course_id)
        .join(User, User.id == Course.instructor_id)
        .add_columns(
            Order.code,
            Order.paid_at,
            Order.coupon_code,
            Order.payment_provider,
            Course.title,
            User.full_name,
            OrderItem.unit_price,
            OrderItem.discount,
            OrderItem.instructor_share_rate,
            INSTRUCTOR_SHARE.label("share"),
        )
        .order_by(Order.paid_at, Order.code, Course.title)
    )
    if instructor_id is not None:
        query = query.where(Course.instructor_id == instructor_id)
    result = []
    for row in await session.execute(query):
        paid = money(row.unit_price - row.discount)
        share = money(row.share)
        result.append(
            SoldLine(
                order_code=row.code,
                paid_at=row.paid_at,
                course_title=row.title,
                instructor_name=row.full_name,
                unit_price=money(row.unit_price),
                discount=money(row.discount),
                paid=paid,
                share_rate=row.instructor_share_rate,
                instructor_share=share,
                platform_share=paid - share,
                coupon_code=row.coupon_code,
                payment_provider=row.payment_provider,
            )
        )
    return result
