"""The demo sales history behind the instructor's dashboard.

The plan is checked without a database: it must never have a buyer pay for a
course twice (checkout would refuse it and stop the script), must stay inside
the year the dashboard can show, and must grow towards today, which is the
shape the "so với kỳ trước" arrows are there to show.

The database test runs the first few purchases through the real checkout and
then reads back what the dashboard reads: paid orders dated in the past, an
enrolment for every line bought, dated with it, and line discounts that add up.
It purges first, inside the test transaction, so a developer machine that has
already run the script tests the same thing a blank CI database does.

A buyer's account is dated before the first thing they did, too: an account
made the morning the script ran would be forty sign-ups in the admin's last
week, from people whose first order is a year old.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import VIETNAM
from app.models import Coupon, Course, Enrollment, Order, OrderItem, User
from scripts.seed import seed_categories
from scripts.seed_courses import seed_courses
from scripts.seed_interactions import build_population, seed_interactions
from scripts.seed_sales import (
    BUYER_COUNT,
    COUPON_CODE,
    HISTORY_DAYS,
    backdate_sign_ups,
    build_plan,
    buyer_emails,
    purchased_at,
    purge,
    seed_sales,
    signed_up,
)
from tests.api.test_commerce import make_user

SLUGS = [f"khoa-{n:02d}" for n in range(24)]


def test_nobody_pays_for_the_same_course_twice() -> None:
    bought: dict[str, list[str]] = {}
    for purchase in build_plan(SLUGS):
        bought.setdefault(purchase.email, []).extend(purchase.slugs)

    for email, slugs in bought.items():
        assert len(slugs) == len(set(slugs)), email
    assert len(bought) == BUYER_COUNT


def test_every_purchase_is_inside_the_year_and_in_order() -> None:
    plan = build_plan(SLUGS)

    assert all(timedelta(0) <= p.ago < timedelta(days=HISTORY_DAYS) for p in plan)
    assert [p.ago for p in plan] == sorted((p.ago for p in plan), reverse=True)


def test_sales_grow_towards_today() -> None:
    plan = build_plan(SLUGS)
    recent = sum(1 for p in plan if p.ago < timedelta(days=HISTORY_DAYS / 2))

    assert recent > len(plan) - recent


def test_a_purchase_lands_on_the_same_day_whatever_time_it_runs() -> None:
    """Counted back from the calendar day, not the moment: run at 07:10 or at
    22:00, every purchase is on the same day -- so the dashboard's days, and
    the studying `scripts.seed_study` starts from them, do not move."""
    early = datetime(2026, 9, 28, 0, 10, tzinfo=UTC)  # 07:10 in Hà Nội
    late = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)  # 22:00
    today = early.astimezone(VIETNAM).date()

    for purchase in build_plan(SLUGS):
        a, b = purchased_at(purchase, early), purchased_at(purchase, late)
        assert a.astimezone(VIETNAM).date() == b.astimezone(VIETNAM).date()
        assert a.astimezone(VIETNAM).date() == today - timedelta(days=purchase.ago.days)
        if purchase.ago.days > 0:
            assert a == b


def test_nobody_buys_in_the_future() -> None:
    for now in (
        datetime(2026, 9, 28, 0, 10, tzinfo=UTC),  # 07:10
        datetime(2026, 9, 28, 15, 0, tzinfo=UTC),  # 22:00
        datetime(2026, 9, 27, 17, 2, tzinfo=UTC),  # 00:02 -- nothing of today has happened
    ):
        moments = [purchased_at(purchase, now) for purchase in build_plan(SLUGS)]
        assert all(at < now for at in moments)
        # Still in the order the plan has them.
        assert moments == sorted(moments)


def test_the_plan_is_the_same_every_time() -> None:
    assert build_plan(SLUGS) == build_plan(list(reversed(SLUGS)))


def test_a_buyer_signs_up_before_the_first_thing_they_do() -> None:
    first = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    joined = {email: signed_up(email, first) for email in buyer_emails()}

    for email, at in joined.items():
        assert first - timedelta(days=31) < at <= first - timedelta(days=1)
        # Seeded with the email, not drawn from the plan: the same every run.
        assert signed_up(email, first) == at
    # Spread out, not forty accounts made in the same minute.
    assert len(set(joined.values())) == BUYER_COUNT


def test_some_purchases_use_the_coupon_and_most_do_not() -> None:
    plan = build_plan(SLUGS)
    share = sum(p.coupon for p in plan) / len(plan)

    assert 0.1 < share < 0.4


async def test_the_purchases_are_what_the_dashboard_reads(db_session: AsyncSession) -> None:
    await seed_categories(db_session)
    await seed_courses(db_session)
    await seed_interactions(db_session, build_population())
    await purge(db_session)
    await db_session.flush()
    now = datetime.now(UTC)

    written = await seed_sales(db_session, now=now, limit=6)

    assert written.orders == 6
    buyers = select(User.id).where(User.email.in_(buyer_emails()))
    orders = list(await db_session.scalars(select(Order).where(Order.user_id.in_(buyers))))
    assert len(orders) == 6
    for order in orders:
        assert order.status == "paid"
        assert now - timedelta(days=HISTORY_DAYS) < order.paid_at <= now
        # Moved back with it, so "đơn tạo lúc" never comes after "đã trả lúc".
        assert order.created_at < order.paid_at

        lines = list(
            await db_session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
        )
        assert sum((line.discount for line in lines), Decimal(0)) == order.discount
        for line in lines:
            enrolment = await db_session.scalar(
                select(Enrollment).where(
                    Enrollment.user_id == order.user_id,
                    Enrollment.course_id == line.course_id,
                )
            )
            assert enrolment is not None
            assert enrolment.source == "purchase"
            assert enrolment.created_at == order.paid_at

    first_paid: dict[uuid.UUID, datetime] = {}
    for order in orders:
        first_paid[order.user_id] = min(first_paid.get(order.user_id, order.paid_at), order.paid_at)
    accounts = await db_session.execute(
        select(User.id, User.email, User.created_at).where(User.id.in_(first_paid))
    )
    for user_id, email, created_at in accounts:
        assert created_at == signed_up(email, first_paid[user_id])
        assert created_at <= first_paid[user_id] - timedelta(days=1)


async def test_a_second_run_writes_nothing_and_purge_takes_it_all_back(
    db_session: AsyncSession,
) -> None:
    await seed_categories(db_session)
    await seed_courses(db_session)
    await seed_interactions(db_session, build_population())
    await purge(db_session)
    await db_session.flush()
    await seed_sales(db_session, limit=3)

    again = await seed_sales(db_session, limit=3)
    assert again.orders == 0

    buyers = select(User.id).where(User.email.in_(buyer_emails()))
    touched = list(
        await db_session.scalars(
            select(Enrollment.course_id).where(Enrollment.user_id.in_(buyers)).distinct()
        )
    )
    assert touched

    await purge(db_session)
    await db_session.flush()

    assert await db_session.scalar(
        select(func.count()).select_from(User).where(User.email.in_(buyer_emails()))
    ) == 0
    assert await db_session.scalar(select(Coupon.id).where(Coupon.code == COUPON_CODE)) is None
    # The courses they had joined count their students right again.
    drift = await db_session.execute(
        select(Course.slug)
        .outerjoin(Enrollment, Enrollment.course_id == Course.id)
        .where(Course.id.in_(touched))
        .group_by(Course.id)
        .having(func.count(Enrollment.id) != Course.students_count)
    )
    assert drift.all() == []


async def test_a_free_course_joined_before_the_first_purchase_moves_the_sign_up_back(
    db_session: AsyncSession,
) -> None:
    """`scripts.seed_study` joins buyers to free courses up to ten weeks back,
    which can be before their first purchase -- so it asks again, and the
    account moves to before the earliest enrolment. Never later."""
    await seed_categories(db_session)
    await seed_courses(db_session)
    slugs = ["python-co-ban-cho-nguoi-moi-bat-dau", "cau-truc-du-lieu-va-giai-thuat-voi-python"]
    free, paid = list(
        await db_session.scalars(
            select(Course).where(Course.slug.in_(slugs)).order_by(Course.price)
        )
    )
    user = await make_user(db_session)
    now = datetime.now(UTC)
    joined_free = now - timedelta(days=50)
    bought = now - timedelta(days=5)
    db_session.add_all(
        [
            Enrollment(user_id=user.id, course_id=free.id, source="free", created_at=joined_free),
            Enrollment(user_id=user.id, course_id=paid.id, source="purchase", created_at=bought),
        ]
    )
    await db_session.flush()

    assert await backdate_sign_ups(db_session, [user.email]) == 1
    created_at = await db_session.scalar(select(User.created_at).where(User.id == user.id))
    assert created_at == signed_up(user.email, joined_free)

    # Asked again, nothing is earlier than that: nothing moves.
    assert await backdate_sign_ups(db_session, [user.email]) == 0
    # And somebody with no enrolment at all is left alone.
    loner = await make_user(db_session)
    assert await backdate_sign_ups(db_session, [loner.email]) == 0
