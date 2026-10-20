"""The admin's leaderboards: one ranking per measure, over one date range.

Each ranking lists every entry with a value, best first, with the value over
the range of the same length just before -- "who moved" is half of what a
leaderboard is for (Stripe Connect's "largest changes"). Ties share a rank and
the next rank skips, as in a race: 1, 2, 2, 4.

Measures that are about quality rather than a period -- rating, completion --
are all-time and carry no previous value, and they need a minimum number of
reviews or learners before an entry is ranked at all: one 5-star review is not
the best course on the platform.

Instructors never see any of this; there is no instructor leaderboard
anywhere (the instructor dashboard compares their own courses only).
"""

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Order,
    OrderItem,
    QaReply,
    QaThread,
    User,
    Wishlist,
)
from app.services import finance
from app.services import instructor_tiers as tiers_service
from app.services.finance import Range
from app.services.stats_calendar import ZERO, money

Unit = Literal["money", "count", "rating", "rate", "hours"]
Value = Decimal | float | int

MIN_REVIEWS = 5
MIN_COMPLETION_BASE = 5
MIN_ANSWERED = 3
SECONDS_PER_HOUR = 3600


@dataclass(frozen=True, slots=True)
class Entry:
    rank: int
    key: str
    label: str
    detail: str | None
    value: Value
    previous: Value | None


@dataclass(frozen=True, slots=True)
class Ranking:
    code: str
    group: str
    title: str
    unit: Unit
    ascending: bool
    entries: list[Entry]
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Concentration:
    """How much of what was paid the biggest instructors account for."""

    top1: float | None
    top5: float | None
    top10: float | None
    instructors: int


@dataclass(frozen=True, slots=True)
class Leaderboards:
    range: Range
    rankings: list[Ranking]
    concentration: Concentration


Rows = dict[Hashable, tuple[str, str | None, Value]]


def _rank(
    code: str,
    group: str,
    title: str,
    unit: Unit,
    current: Rows,
    previous: Rows | None,
    *,
    ascending: bool = False,
    note: str | None = None,
) -> Ranking:
    items = sorted(
        current.items(),
        key=lambda item: (item[1][2] if ascending else -item[1][2], item[1][0]),
    )
    entries: list[Entry] = []
    last_value: Value | None = None
    rank = 0
    for position, (key, (label, detail, value)) in enumerate(items, start=1):
        if value != last_value:
            rank = position
            last_value = value
        before = None
        if previous is not None and key in previous:
            before = previous[key][2]
        elif previous is not None and unit in ("money", "count"):
            # Nothing in the range before is a zero, not a gap.
            before = 0
        entries.append(Entry(rank, str(key), label, detail, value, before))
    return Ranking(code, group, title, unit, ascending, entries, note)


# --- Instructors -------------------------------------------------------------


async def _instructor_money(session: AsyncSession, span: Range) -> tuple[Rows, Rows, Rows]:
    paid: Rows = {}
    share: Rows = {}
    sales: Rows = {}
    for item in await finance.by_instructor(session, span):
        user = item.instructor
        assert user is not None
        tier = item.tier.name if item.tier else None
        paid[user.id] = (user.full_name, tier, item.paid)
        share[user.id] = (user.full_name, tier, item.instructor_share)
        sales[user.id] = (user.full_name, tier, item.lines)
    return paid, share, sales


async def _instructor_new_students(session: AsyncSession, span: Range) -> Rows:
    start, stop = span.bounds()
    first = (
        select(
            Course.instructor_id,
            Enrollment.user_id,
            func.min(Enrollment.created_at).label("first_at"),
        )
        .join(Course, Course.id == Enrollment.course_id)
        .group_by(Course.instructor_id, Enrollment.user_id)
        .subquery()
    )
    rows = await session.execute(
        select(User.id, User.full_name, func.count())
        .join(first, first.c.instructor_id == User.id)
        .where(first.c.first_at >= start, first.c.first_at < stop)
        .group_by(User.id)
    )
    return {user_id: (name, None, count) for user_id, name, count in rows}


async def _instructor_response(session: AsyncSession, span: Range) -> Rows:
    """Median hours to the instructor's first answer, for learners' questions
    asked in the range that got one."""
    start, stop = span.bounds()
    first_reply = (
        select(QaReply.thread_id, func.min(QaReply.created_at).label("at"))
        .where(QaReply.is_instructor_reply.is_(True))
        .group_by(QaReply.thread_id)
        .subquery()
    )
    hours = func.extract("epoch", first_reply.c.at - QaThread.created_at) / SECONDS_PER_HOUR
    rows = await session.execute(
        select(
            User.id,
            User.full_name,
            func.count(),
            func.percentile_cont(0.5).within_group(hours),
        )
        .select_from(QaThread)
        .join(first_reply, first_reply.c.thread_id == QaThread.id)
        .join(Lesson, Lesson.id == QaThread.lesson_id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .join(Course, Course.id == CourseSection.course_id)
        .join(User, User.id == Course.instructor_id)
        .where(
            QaThread.user_id != Course.instructor_id,
            QaThread.created_at >= start,
            QaThread.created_at < stop,
        )
        .group_by(User.id)
    )
    return {
        user_id: (name, f"{count} câu đã trả lời", round(float(median), 1))
        for user_id, name, count, median in rows
        if count >= MIN_ANSWERED
    }


# --- Courses -----------------------------------------------------------------


async def _course_money(session: AsyncSession, span: Range) -> tuple[Rows, Rows]:
    paid: Rows = {}
    sales: Rows = {}
    for item in await finance.by_course(session, span):
        course, instructor = item.course, item.instructor
        assert course is not None and instructor is not None
        paid[course.id] = (course.title, instructor.full_name, item.paid)
        sales[course.id] = (course.title, instructor.full_name, item.lines)
    return paid, sales


async def _course_counts(session: AsyncSession, span: Range, column, model) -> Rows:
    start, stop = span.bounds()
    rows = await session.execute(
        select(Course.id, Course.title, User.full_name, func.count())
        .select_from(model)
        .join(Course, Course.id == model.course_id)
        .join(User, User.id == Course.instructor_id)
        .where(column >= start, column < stop)
        .group_by(Course.id, User.id)
    )
    return {course_id: (title, name, count) for course_id, title, name, count in rows}


async def _course_rating(session: AsyncSession) -> Rows:
    rows = await session.execute(
        select(Course.id, Course.title, User.full_name, Course.rating_avg, Course.rating_count)
        .join(User, User.id == Course.instructor_id)
        .where(Course.rating_count >= MIN_REVIEWS, Course.deleted_at.is_(None))
    )
    return {
        course_id: (title, f"{name} · {count} đánh giá", round(float(avg), 2))
        for course_id, title, name, avg, count in rows
    }


# --- Coupons, categories -----------------------------------------------------


async def _coupons(session: AsyncSession, span: Range) -> tuple[Rows, Rows, Rows]:
    start, stop = span.bounds()
    rows = await session.execute(
        select(
            Order.coupon_code,
            func.count(),
            func.coalesce(func.sum(Order.discount), 0),
            func.coalesce(func.sum(Order.total), 0),
        )
        .where(
            Order.status == "paid",
            Order.coupon_code.is_not(None),
            Order.paid_at >= start,
            Order.paid_at < stop,
        )
        .group_by(Order.coupon_code)
    )
    uses: Rows = {}
    discount: Rows = {}
    paid: Rows = {}
    for code, count, off, total in rows:
        uses[code] = (code, None, count)
        discount[code] = (code, None, money(off))
        paid[code] = (code, None, money(total))
    return uses, discount, paid


async def _categories(session: AsyncSession, span: Range) -> tuple[Rows, Rows]:
    start, stop = span.bounds()
    paid_rows = await session.execute(
        select(Category.id, Category.name, func.coalesce(func.sum(finance.PAID), 0))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Course, Course.id == OrderItem.course_id)
        .join(Category, Category.id == Course.category_id)
        .where(Order.status == "paid", Order.paid_at >= start, Order.paid_at < stop)
        .group_by(Category.id)
    )
    paid: Rows = {cid: (name, None, money(total)) for cid, name, total in paid_rows}
    joined_rows = await session.execute(
        select(Category.id, Category.name, func.count())
        .select_from(Enrollment)
        .join(Course, Course.id == Enrollment.course_id)
        .join(Category, Category.id == Course.category_id)
        .where(Enrollment.created_at >= start, Enrollment.created_at < stop)
        .group_by(Category.id)
    )
    joined: Rows = {cid: (name, None, count) for cid, name, count in joined_rows}
    return paid, joined


# --- All of it ---------------------------------------------------------------


def _concentration(paid: Rows) -> Concentration:
    values = sorted((Decimal(value) for _, _, value in paid.values()), reverse=True)
    total = sum(values, ZERO)

    def top(n: int) -> float | None:
        return round(float(sum(values[:n], ZERO) / total), 4) if total else None

    return Concentration(top(1), top(5), top(10), len(values))


async def leaderboards(session: AsyncSession, span: Range) -> Leaderboards:
    before = span.previous()

    async def both(fetch: Callable) -> tuple:
        return await fetch(span), await fetch(before)

    (paid, share, sales), (paid_prev, share_prev, sales_prev) = await both(
        lambda r: _instructor_money(session, r)
    )
    new_students, new_students_prev = await both(lambda r: _instructor_new_students(session, r))
    response, response_prev = await both(lambda r: _instructor_response(session, r))

    evaluations = await tiers_service.evaluate_all(session)
    rating: Rows = {}
    completion: Rows = {}
    for evaluation in evaluations:
        user, metrics = evaluation.instructor, evaluation.metrics
        if metrics.rating is not None and metrics.reviews >= MIN_REVIEWS:
            rating[user.id] = (
                user.full_name,
                f"{metrics.reviews} đánh giá của người mua",
                metrics.rating,
            )
        if metrics.completion_rate is not None and metrics.completion_base >= MIN_COMPLETION_BASE:
            completion[user.id] = (
                user.full_name,
                f"{metrics.completion_base} lượt ghi danh trả phí",
                metrics.completion_rate,
            )

    (course_paid, course_sales), (course_paid_prev, course_sales_prev) = await both(
        lambda r: _course_money(session, r)
    )
    joined, joined_prev = await both(
        lambda r: _course_counts(session, r, Enrollment.created_at, Enrollment)
    )
    wished, wished_prev = await both(
        lambda r: _course_counts(session, r, Wishlist.created_at, Wishlist)
    )
    (uses, off, coupon_paid), (uses_prev, off_prev, coupon_paid_prev) = await both(
        lambda r: _coupons(session, r)
    )
    (category_paid, category_joined), (category_paid_prev, category_joined_prev) = await both(
        lambda r: _categories(session, r)
    )

    rankings = [
        _rank(
            "instructor_paid",
            "instructors",
            "Doanh thu theo giảng viên",
            "money",
            paid,
            paid_prev,
        ),
        _rank(
            "instructor_share",
            "instructors",
            "Hoa hồng giảng viên",
            "money",
            share,
            share_prev,
        ),
        _rank(
            "instructor_new_students",
            "instructors",
            "Học viên mới",
            "count",
            new_students,
            new_students_prev,
        ),
        _rank("instructor_sales", "instructors", "Lượt bán", "count", sales, sales_prev),
        _rank(
            "instructor_rating",
            "instructors",
            "Đánh giá (Bayes, người mua)",
            "rating",
            rating,
            None,
            note=f"Từ trước tới nay; cần ít nhất {MIN_REVIEWS} đánh giá.",
        ),
        _rank(
            "instructor_completion",
            "instructors",
            "Tỉ lệ hoàn thành",
            "rate",
            completion,
            None,
            note=(f"Lượt ghi danh trả phí đã quá 30 ngày; cần ít nhất {MIN_COMPLETION_BASE} lượt."),
        ),
        _rank(
            "instructor_response",
            "instructors",
            "Thời gian trả lời Hỏi đáp (trung vị)",
            "hours",
            response,
            response_prev,
            ascending=True,
            note=f"Cần ít nhất {MIN_ANSWERED} câu đã trả lời trong kỳ.",
        ),
        _rank(
            "course_paid",
            "courses",
            "Doanh thu theo khóa học",
            "money",
            course_paid,
            course_paid_prev,
        ),
        _rank(
            "course_sales",
            "courses",
            "Lượt bán theo khóa học",
            "count",
            course_sales,
            course_sales_prev,
        ),
        _rank("course_enrollments", "courses", "Ghi danh mới", "count", joined, joined_prev),
        _rank(
            "course_rating",
            "courses",
            "Điểm đánh giá khóa học",
            "rating",
            await _course_rating(session),
            None,
            note=f"Từ trước tới nay; cần ít nhất {MIN_REVIEWS} đánh giá.",
        ),
        _rank("course_wishlist", "courses", "Thêm vào yêu thích", "count", wished, wished_prev),
        _rank("coupon_uses", "coupons", "Lượt dùng mã giảm giá", "count", uses, uses_prev),
        _rank("coupon_discount", "coupons", "Tiền giảm theo mã", "money", off, off_prev),
        _rank(
            "coupon_paid",
            "coupons",
            "Doanh thu từ đơn có mã",
            "money",
            coupon_paid,
            coupon_paid_prev,
        ),
        _rank(
            "category_paid",
            "categories",
            "Doanh thu theo danh mục",
            "money",
            category_paid,
            category_paid_prev,
        ),
        _rank(
            "category_enrollments",
            "categories",
            "Ghi danh theo danh mục",
            "count",
            category_joined,
            category_joined_prev,
        ),
    ]
    return Leaderboards(range=span, rankings=rankings, concentration=_concentration(paid))
