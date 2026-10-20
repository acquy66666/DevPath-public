"""Instructor tiers: the numbers, the suggestion, and the admin's decision.

**The system suggests, an admin decides.** `evaluate_all` reads every
instructor's numbers and checks them against each tier's thresholds; the
highest tier whose every criterion is met is the *suggestion*. Nothing moves
until an admin calls `set_tier`, with a note, and that decision is written to
`instructor_tier_changes` with the numbers it was made on. This is the shape of
Fiverr's Top Rated and Upwork's Expert-Vetted: computed eligibility, human
approval (docs/thiet-ke-cap-bac-va-tai-chinh.md, section 3).

**What each number means**, so it is hard to pump with a second account:

* **Paid students** -- distinct buyers of the instructor's courses whose line
  cost them at least 30 % of its list price and at least 10 000 đ, in a paid
  order that went through a gateway (a 0 đ order, a 100 % code, does not
  count), from an account that is not locked.
* **Revenue (12 months)** -- what buyers paid for the instructor's lines
  (`unit_price - discount`) in the last 365 days. Admin-only.
* **Rating** -- a Bayesian average of reviews written by people who *bought*
  the course: (sum + 4.0 x 10) / (count + 10), so five 5-star reviews from
  friends do not make a 5.0. The tier also asks for a minimum count.
* **Completion** -- of paid enrolments at least 30 days old, the share that
  finished (a younger enrolment has not had the time to).
* **Q&A** -- of learners' questions in the last 90 days that are at least
  48 hours old, the share the instructor answered within 48 hours. Fewer than
  five such questions counts as met: there is not enough to judge.
* **Months active** -- whole months since the instructor's first course went
  on sale. **Published courses** -- on sale now.
* Above the first tier, an account must not be locked and must not have had a
  course taken down after a report in the last 90 days.

**Keeping a tier is easier than reaching it** (no flapping around a line):
the maintenance bar is 80 % of the entry bar for students and revenue, 0.2
stars below for rating and 10 points below for the two rates. Falling under it
only *flags* the instructor for an admin; nothing is demoted automatically.

**The instructor never sees a number with money in it.** `my_tier` reports
paid students and revenue as met / not met, with no value and no threshold
-- buyers times the public price is revenue.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import DomainError
from app.models import (
    NOTIFICATION_INSTRUCTOR_TIER_CHANGED,
    Course,
    CourseSection,
    Enrollment,
    InstructorTier,
    InstructorTierChange,
    Lesson,
    Order,
    OrderItem,
    QaReply,
    QaThread,
    Report,
    Review,
    User,
)
from app.services import notifications as notifications_service
from app.services.stats_calendar import money

PAID_STUDENT_MIN_SHARE = Decimal("0.30")
PAID_STUDENT_MIN_AMOUNT = Decimal("10000")
REVENUE_WINDOW = timedelta(days=365)
BAYES_PRIOR = 4.0
BAYES_WEIGHT = 10
COMPLETION_MIN_AGE = timedelta(days=30)
QA_WINDOW = timedelta(days=90)
QA_ANSWER_WITHIN = timedelta(hours=48)
QA_MIN_QUESTIONS = 5
REPORT_WINDOW = timedelta(days=90)
#: Maintenance bar, relative to the entry bar of the tier one holds.
MAINTAIN_COUNT_FACTOR = Decimal("0.8")
MAINTAIN_RATING_MARGIN = Decimal("0.2")
MAINTAIN_RATE_MARGIN = Decimal("0.10")
#: Shown to the admin as a caution, not enforced: a tier just granted is not
#: taken away over one bad month, and the top tier is not skipped to.
RECENT_CHANGE = timedelta(days=182)

RATE_PLACES = 4


class InstructorNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "INSTRUCTOR_NOT_FOUND"


class TierNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "TIER_NOT_FOUND"


class TierUnchangedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "TIER_UNCHANGED"


class TierLadderError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "TIER_LADDER_BROKEN"


# --- Tiers -------------------------------------------------------------------


async def list_tiers(session: AsyncSession) -> list[InstructorTier]:
    return list(await session.scalars(select(InstructorTier).order_by(InstructorTier.rank)))


def _base(tiers: list[InstructorTier]) -> InstructorTier:
    return tiers[0]


def _tier_of(user: User, tiers: list[InstructorTier]) -> InstructorTier:
    if user.instructor_tier_id is None:
        return _base(tiers)
    return next(tier for tier in tiers if tier.id == user.instructor_tier_id)


async def share_rates(
    session: AsyncSession, course_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    """The share each course's instructor gets on a sale made now."""
    if not course_ids:
        return {}
    base_rate = await session.scalar(
        select(InstructorTier.share_rate).where(InstructorTier.rank == 1)
    )
    rows = await session.execute(
        select(Course.id, InstructorTier.share_rate)
        .join(User, User.id == Course.instructor_id)
        .outerjoin(InstructorTier, InstructorTier.id == User.instructor_tier_id)
        .where(Course.id.in_(course_ids))
    )
    return {course_id: rate or base_rate for course_id, rate in rows}


async def update_tier(
    session: AsyncSession, tier_id: uuid.UUID, changes: dict[str, Any]
) -> InstructorTier:
    """Edit a tier's name, description, rate or thresholds.

    The ladder must stay a ladder: each rate at least the one below it and at
    most the one above. A new rate changes what is sold from now on only --
    every sale carries the rate it was made at.
    """
    tiers = await list_tiers(session)
    tier = next((t for t in tiers if t.id == tier_id), None)
    if tier is None:
        raise TierNotFoundError("Không tìm thấy cấp giảng viên này")

    rate = changes.get("share_rate", tier.share_rate)
    below = next((t for t in tiers if t.rank == tier.rank - 1), None)
    above = next((t for t in tiers if t.rank == tier.rank + 1), None)
    if below is not None and rate < below.share_rate:
        raise TierLadderError(
            f"Tỉ lệ chia của “{tier.name}” không được thấp hơn cấp dưới “{below.name}”"
        )
    if above is not None and rate > above.share_rate:
        raise TierLadderError(
            f"Tỉ lệ chia của “{tier.name}” không được cao hơn cấp trên “{above.name}”"
        )

    for name, value in changes.items():
        setattr(tier, name, value)
    await session.commit()
    await session.refresh(tier)
    return tier


# --- Metrics -----------------------------------------------------------------


@dataclass(slots=True)
class Metrics:
    paid_students: int = 0
    revenue_12m: Decimal = Decimal("0.00")
    reviews: int = 0
    rating_raw: float | None = None
    rating: float | None = None
    completion_rate: float | None = None
    completion_base: int = 0
    qa_questions: int = 0
    qa_answer_rate: float | None = None
    published_courses: int = 0
    first_published_at: datetime | None = None
    months_active: int = 0
    removed_courses_90d: int = 0
    locked: bool = False

    def as_json(self) -> dict[str, Any]:
        return {
            "paid_students": self.paid_students,
            "revenue_12m": str(self.revenue_12m),
            "reviews": self.reviews,
            "rating_raw": self.rating_raw,
            "rating": self.rating,
            "completion_rate": self.completion_rate,
            "completion_base": self.completion_base,
            "qa_questions": self.qa_questions,
            "qa_answer_rate": self.qa_answer_rate,
            "published_courses": self.published_courses,
            "first_published_at": (
                self.first_published_at.isoformat() if self.first_published_at else None
            ),
            "months_active": self.months_active,
            "removed_courses_90d": self.removed_courses_90d,
            "locked": self.locked,
        }


def _months_between(start: datetime, end: datetime) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    if (end.day, end.time()) < (start.day, start.time()):
        months -= 1
    return max(months, 0)


async def _metrics(
    session: AsyncSession, instructor_ids: list[uuid.UUID], now: datetime
) -> dict[uuid.UUID, Metrics]:
    """Every metric, for many instructors at once -- one query per metric."""
    found = {instructor_id: Metrics() for instructor_id in instructor_ids}
    if not instructor_ids:
        return found
    teaches = Course.instructor_id.in_(instructor_ids)

    net = OrderItem.unit_price - OrderItem.discount
    buyer = User.__table__.alias("buyer")
    for instructor_id, students in await session.execute(
        select(Course.instructor_id, func.count(func.distinct(Order.user_id)))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Course, Course.id == OrderItem.course_id)
        .join(buyer, buyer.c.id == Order.user_id)
        .where(
            teaches,
            Order.status == "paid",
            Order.payment_provider != "none",
            net >= OrderItem.unit_price * PAID_STUDENT_MIN_SHARE,
            net >= PAID_STUDENT_MIN_AMOUNT,
            buyer.c.locked_at.is_(None),
        )
        .group_by(Course.instructor_id)
    ):
        found[instructor_id].paid_students = students

    for instructor_id, revenue in await session.execute(
        select(Course.instructor_id, func.sum(net))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Course, Course.id == OrderItem.course_id)
        .where(teaches, Order.status == "paid", Order.paid_at >= now - REVENUE_WINDOW)
        .group_by(Course.instructor_id)
    ):
        found[instructor_id].revenue_12m = money(revenue)

    bought = and_(
        Enrollment.user_id == Review.user_id,
        Enrollment.course_id == Review.course_id,
        Enrollment.source == "purchase",
    )
    for instructor_id, count, total in await session.execute(
        select(Course.instructor_id, func.count(), func.sum(Review.rating))
        .select_from(Review)
        .join(Course, Course.id == Review.course_id)
        .join(Enrollment, bought)
        .where(teaches)
        .group_by(Course.instructor_id)
    ):
        metrics = found[instructor_id]
        metrics.reviews = count
        metrics.rating_raw = round(total / count, 2)
        metrics.rating = round((total + BAYES_PRIOR * BAYES_WEIGHT) / (count + BAYES_WEIGHT), 2)

    for instructor_id, base, completed in await session.execute(
        select(Course.instructor_id, func.count(), func.count(Enrollment.completed_at))
        .select_from(Enrollment)
        .join(Course, Course.id == Enrollment.course_id)
        .where(
            teaches,
            Enrollment.source == "purchase",
            Enrollment.created_at <= now - COMPLETION_MIN_AGE,
        )
        .group_by(Course.instructor_id)
    ):
        found[instructor_id].completion_base = base
        found[instructor_id].completion_rate = (
            round(completed / base, RATE_PLACES) if base else None
        )

    first_reply = (
        select(QaReply.thread_id, func.min(QaReply.created_at).label("at"))
        .where(QaReply.is_instructor_reply.is_(True))
        .group_by(QaReply.thread_id)
        .subquery()
    )
    for instructor_id, questions, answered in await session.execute(
        select(
            Course.instructor_id,
            func.count(),
            func.count().filter(first_reply.c.at - QaThread.created_at <= QA_ANSWER_WITHIN),
        )
        .select_from(QaThread)
        .join(Lesson, Lesson.id == QaThread.lesson_id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .join(Course, Course.id == CourseSection.course_id)
        .outerjoin(first_reply, first_reply.c.thread_id == QaThread.id)
        .where(
            teaches,
            QaThread.user_id != Course.instructor_id,
            QaThread.created_at >= now - QA_WINDOW,
            QaThread.created_at <= now - QA_ANSWER_WITHIN,
        )
        .group_by(Course.instructor_id)
    ):
        found[instructor_id].qa_questions = questions
        found[instructor_id].qa_answer_rate = (
            round(answered / questions, RATE_PLACES) if questions else None
        )

    for instructor_id, published, first in await session.execute(
        select(
            Course.instructor_id,
            func.count().filter(Course.status == "published", Course.deleted_at.is_(None)),
            func.min(Course.published_at),
        )
        .where(teaches)
        .group_by(Course.instructor_id)
    ):
        metrics = found[instructor_id]
        metrics.published_courses = published
        metrics.first_published_at = first
        metrics.months_active = _months_between(first, now) if first else 0

    for instructor_id, removed in await session.execute(
        select(Course.instructor_id, func.count(func.distinct(Report.target_id)))
        .select_from(Report)
        .join(Course, Course.id == Report.target_id)
        .where(
            teaches,
            Report.target_type == "course",
            Report.content_removed.is_(True),
            Report.resolved_at >= now - REPORT_WINDOW,
        )
        .group_by(Course.instructor_id)
    ):
        found[instructor_id].removed_courses_90d = removed

    for instructor_id, locked_at in await session.execute(
        select(User.id, User.locked_at).where(User.id.in_(instructor_ids))
    ):
        found[instructor_id].locked = locked_at is not None

    return found


# --- Checks ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Criterion:
    key: str
    label: str
    #: The instructor's value, formatted for reading ("4,52 sao (37 đánh giá)").
    value: str
    #: What the tier asks for, formatted the same way.
    threshold: str
    met: bool
    #: Money, or a count that is money in disguise: the instructor is told
    #: only whether it is met.
    admin_only: bool = False


@dataclass(frozen=True, slots=True)
class TierCheck:
    tier: InstructorTier
    criteria: list[Criterion]

    @property
    def met(self) -> bool:
        return all(criterion.met for criterion in self.criteria)


def _vnd(amount: Decimal) -> str:
    return f"{int(amount):,}".replace(",", ".") + " đ"


def _pct(value: float | Decimal | None) -> str:
    return "—" if value is None else f"{float(value) * 100:.0f}%".replace(".", ",")


def _stars(value: float | Decimal | None) -> str:
    return "—" if value is None else f"{float(value):.2f}".replace(".", ",")


def check(tier: InstructorTier, metrics: Metrics, *, maintain: bool = False) -> TierCheck:
    """`metrics` against `tier`'s bar -- its entry bar, or with `maintain` the
    lower one an instructor already on the tier has to keep above."""
    if tier.rank == 1:
        return TierCheck(tier, [])

    count_factor = MAINTAIN_COUNT_FACTOR if maintain else Decimal(1)
    rating_margin = MAINTAIN_RATING_MARGIN if maintain else Decimal(0)
    rate_margin = MAINTAIN_RATE_MARGIN if maintain else Decimal(0)

    criteria: list[Criterion] = []
    need_courses = tier.min_published_courses
    criteria.append(
        Criterion(
            "published_courses",
            "Khóa học đang bán",
            str(metrics.published_courses),
            f"≥ {need_courses}",
            metrics.published_courses >= need_courses,
        )
    )
    criteria.append(
        Criterion(
            "months_active",
            "Thời gian giảng dạy",
            f"{metrics.months_active} tháng",
            f"≥ {tier.min_months_active} tháng",
            metrics.months_active >= tier.min_months_active,
        )
    )
    need_students = int(Decimal(tier.min_paid_students) * count_factor)
    criteria.append(
        Criterion(
            "paid_students",
            "Học viên trả phí",
            str(metrics.paid_students),
            f"≥ {need_students}",
            metrics.paid_students >= need_students,
            admin_only=True,
        )
    )
    need_revenue = (tier.min_revenue_12m * count_factor).quantize(Decimal("1"))
    criteria.append(
        Criterion(
            "revenue_12m",
            "Doanh thu 12 tháng",
            _vnd(metrics.revenue_12m),
            f"≥ {_vnd(need_revenue)}",
            metrics.revenue_12m >= need_revenue,
            admin_only=True,
        )
    )
    if tier.min_rating is not None:
        need_rating = tier.min_rating - rating_margin
        criteria.append(
            Criterion(
                "rating",
                "Đánh giá của học viên trả phí",
                f"{_stars(metrics.rating)} sao ({metrics.reviews} đánh giá)",
                f"≥ {_stars(need_rating)} sao, ≥ {tier.min_reviews} đánh giá",
                metrics.rating is not None
                and metrics.reviews >= tier.min_reviews
                and Decimal(str(metrics.rating)) >= need_rating,
            )
        )
    if tier.min_completion_rate is not None:
        need_completion = tier.min_completion_rate - rate_margin
        criteria.append(
            Criterion(
                "completion_rate",
                "Tỉ lệ hoàn thành khóa",
                _pct(metrics.completion_rate),
                f"≥ {_pct(need_completion)}",
                metrics.completion_rate is not None
                and Decimal(str(metrics.completion_rate)) >= need_completion,
            )
        )
    if tier.min_qa_answer_rate is not None:
        need_qa = tier.min_qa_answer_rate - rate_margin
        few = metrics.qa_questions < QA_MIN_QUESTIONS
        criteria.append(
            Criterion(
                "qa_answer_rate",
                "Trả lời Hỏi đáp trong 48 giờ (90 ngày)",
                (
                    f"{metrics.qa_questions} câu hỏi — chưa đủ để xét"
                    if few
                    else f"{_pct(metrics.qa_answer_rate)} của {metrics.qa_questions} câu"
                ),
                f"≥ {_pct(need_qa)}",
                few or Decimal(str(metrics.qa_answer_rate)) >= need_qa,
            )
        )
    criteria.append(
        Criterion(
            "good_standing",
            "Tài khoản không bị khóa, không có khóa học bị gỡ do vi phạm (90 ngày)",
            "Đạt" if not metrics.locked and metrics.removed_courses_90d == 0 else "Chưa đạt",
            "Bắt buộc",
            not metrics.locked and metrics.removed_courses_90d == 0,
        )
    )
    return TierCheck(tier, criteria)


# --- Evaluation --------------------------------------------------------------


@dataclass(slots=True)
class Evaluation:
    instructor: User
    current: InstructorTier
    metrics: Metrics
    checks: list[TierCheck]
    suggested: InstructorTier
    #: Whether the instructor is still above the bar of the tier they hold.
    keeps_current: bool
    last_change: InstructorTierChange | None
    flags: list[str] = field(default_factory=list)

    @property
    def next_check(self) -> TierCheck | None:
        return next((c for c in self.checks if c.tier.rank == self.current.rank + 1), None)


def _evaluate(
    user: User,
    tiers: list[InstructorTier],
    metrics: Metrics,
    last_change: InstructorTierChange | None,
    now: datetime,
) -> Evaluation:
    current = _tier_of(user, tiers)
    checks = [check(tier, metrics) for tier in tiers]
    suggested = _base(tiers)
    for result in checks:
        if result.met:
            suggested = result.tier
    keeps = check(current, metrics, maintain=True).met

    flags: list[str] = []
    if suggested.rank > current.rank:
        flags.append("eligible")
    if not keeps:
        flags.append("below_maintenance")
    if last_change is not None and now - last_change.created_at < RECENT_CHANGE:
        flags.append("recently_changed")
    if suggested.rank == len(tiers) and current.rank < len(tiers) - 1:
        # The top tier is reached from the one below it, after time spent there.
        flags.append("top_tier_skips_a_step")
    return Evaluation(
        instructor=user,
        current=current,
        metrics=metrics,
        checks=checks,
        suggested=suggested,
        keeps_current=keeps,
        last_change=last_change,
        flags=flags,
    )


async def _last_changes(
    session: AsyncSession, instructor_ids: list[uuid.UUID]
) -> dict[uuid.UUID, InstructorTierChange]:
    if not instructor_ids:
        return {}
    ranked = (
        select(
            InstructorTierChange.id,
            func.row_number()
            .over(
                partition_by=InstructorTierChange.instructor_id,
                order_by=InstructorTierChange.created_at.desc(),
            )
            .label("n"),
        )
        .where(InstructorTierChange.instructor_id.in_(instructor_ids))
        .subquery()
    )
    rows = await session.scalars(
        select(InstructorTierChange)
        .join(ranked, ranked.c.id == InstructorTierChange.id)
        .where(ranked.c.n == 1)
    )
    return {row.instructor_id: row for row in rows}


async def evaluate_all(session: AsyncSession, *, now: datetime | None = None) -> list[Evaluation]:
    """Every instructor, with their numbers and what they would qualify for."""
    moment = now or datetime.now(UTC)
    tiers = await list_tiers(session)
    users = list(
        await session.scalars(
            select(User).where(User.role == "instructor").order_by(User.full_name, User.id)
        )
    )
    ids = [user.id for user in users]
    metrics = await _metrics(session, ids, moment)
    last = await _last_changes(session, ids)
    return [_evaluate(user, tiers, metrics[user.id], last.get(user.id), moment) for user in users]


async def evaluate(
    session: AsyncSession, instructor_id: uuid.UUID, *, now: datetime | None = None
) -> Evaluation:
    moment = now or datetime.now(UTC)
    user = await session.get(User, instructor_id)
    if user is None or user.role != "instructor":
        raise InstructorNotFoundError("Không tìm thấy giảng viên này")
    tiers = await list_tiers(session)
    metrics = await _metrics(session, [user.id], moment)
    last = await _last_changes(session, [user.id])
    return _evaluate(user, tiers, metrics[user.id], last.get(user.id), moment)


async def history(
    session: AsyncSession, instructor_id: uuid.UUID
) -> list[tuple[InstructorTierChange, InstructorTier | None, InstructorTier, User | None]]:
    """Every decision about one instructor, newest first, with both tiers and
    the admin who made it."""
    to_tier = aliased(InstructorTier)
    from_tier = aliased(InstructorTier)
    decider = aliased(User)
    rows = await session.execute(
        select(InstructorTierChange, from_tier, to_tier, decider)
        .join(to_tier, to_tier.id == InstructorTierChange.to_tier_id)
        .outerjoin(from_tier, from_tier.id == InstructorTierChange.from_tier_id)
        .outerjoin(decider, decider.id == InstructorTierChange.decided_by)
        .where(InstructorTierChange.instructor_id == instructor_id)
        .order_by(InstructorTierChange.created_at.desc(), InstructorTierChange.id.desc())
    )
    return [tuple(row) for row in rows]


async def set_tier(
    session: AsyncSession,
    admin: User,
    instructor_id: uuid.UUID,
    tier_id: uuid.UUID,
    note: str,
    *,
    now: datetime | None = None,
) -> Evaluation:
    """An admin's decision: move this instructor to that tier, for this reason.

    The instructor's row is locked first, so two admins deciding at once
    cannot both write a change from the same tier. The numbers the decision
    was made on are stored with it, and the instructor is told in the same
    transaction. Sales already paid keep the rate they were made at.
    """
    moment = now or datetime.now(UTC)
    user = await session.scalar(select(User).where(User.id == instructor_id).with_for_update())
    if user is None or user.role != "instructor":
        raise InstructorNotFoundError("Không tìm thấy giảng viên này")

    tiers = await list_tiers(session)
    target = next((tier for tier in tiers if tier.id == tier_id), None)
    if target is None:
        raise TierNotFoundError("Không tìm thấy cấp giảng viên này")
    current = _tier_of(user, tiers)
    if target.id == current.id:
        raise TierUnchangedError(f"Giảng viên này đang ở cấp “{current.name}”")

    metrics = (await _metrics(session, [user.id], moment))[user.id]
    session.add(
        InstructorTierChange(
            instructor_id=user.id,
            from_tier_id=current.id,
            to_tier_id=target.id,
            decided_by=admin.id,
            note=note,
            metrics=metrics.as_json(),
            created_at=moment,
        )
    )
    user.instructor_tier_id = target.id
    notifications_service.add(
        session,
        user_id=user.id,
        type=NOTIFICATION_INSTRUCTOR_TIER_CHANGED,
        payload={
            "from_tier": current.name,
            "from_rank": current.rank,
            "to_tier": target.name,
            "to_rank": target.rank,
            "share_rate": str(target.share_rate),
            "note": note,
        },
    )
    await session.commit()
    return await evaluate(session, user.id, now=moment)
