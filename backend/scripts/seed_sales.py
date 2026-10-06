"""A year of sales, so the instructor's dashboard opens on real-looking numbers.

    python -m scripts.seed_sales
    python -m scripts.seed_sales --purge

The dashboard reads paid orders and enrolments by *when* they happened, and
nothing else on a development machine happens on more than one day: every
seeded enrolment is stamped with the morning `scripts.seed_interactions` ran,
and a payment is something a person does by hand, once. So the chart would be
one spike and a flat line. This writes orders spread over the past twelve
months, more of them recently, by forty buyers of its own -- out of whatever
paid courses are on sale: 77 orders (139 courses sold) with the synthetic
courses of `scripts.seed_interactions`, 40 orders of the one paid course once
those are purged, as they are for the defence.

**Every purchase goes through the real checkout.** Courses go into a cart via
`commerce.add_to_cart`, the cart becomes an order via `orders.create_from_cart`
(a quarter of them with a coupon, so the per-line discount split is exercised),
and the order is paid by a VNPay callback signed and handed to
`orders.handle_vnpay_ipn` -- the handler that enrols the buyer, uses up the
coupon and logs the event. A purchase this script can make is one a person
could have made.

**The one thing written directly is the clock.** The services stamp rows with
`now()`; afterwards the order, its enrolments and its payment event are moved
back to the moment the plan says the purchase happened. `paid_at` needs no
moving -- the callback is handed that moment.

The callback is signed with a **local secret**, not the merchant's: the
settings object given to the handler is a copy carrying it, so this runs on a
machine with no VNPay account and never touches the real credentials.

**Its own buyers** (`nguoimuaNN@sales.devpath.example`), not the seeded
learners: `scripts.seed_interactions` and its tests pin exactly which course
each learner is enrolled in, and a purchase by one of them would move that.
These enrolments do feed the recommender like any other, so **run `--purge`
before measuring it** with `scripts.eval_recommender`.

Dates are **relative to when it runs** -- the plan is a fixed list of "N days
ago", like `scripts.seed_coupons` -- so the dashboard never ages into an empty
last month. Idempotent: if the buyers exist, it writes nothing. `--purge`
removes the buyers, their orders and enrolments and its coupon, and recounts
the students of every course they had joined.
"""

import argparse
import asyncio
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Coupon, Course, Enrollment, Order, PaymentEvent, User
from app.services import certificates, course_stats, vnpay
from app.services import commerce as commerce_service
from app.services import orders as orders_service

BUYER_COUNT = 40
BUYER_EMAIL = "nguoimua{:02d}@sales.devpath.example"
BUYER_PASSWORD = "devpath-buyer"

#: Site-wide, 20 %, no limit on uses, live since before the first purchase.
COUPON_CODE = "BANHANG20"
COUPON_SHARE = 0.25

HISTORY_DAYS = 365
#: Fixed, so every machine gets the same purchases -- only the dates they are
#: counted back from differ.
RANDOM_SEED = 20260924

LOCAL_TMN_CODE = "SEEDSALE"
LOCAL_SECRET = "seed-sales-local-secret"


@dataclass(frozen=True, slots=True)
class Purchase:
    email: str
    slugs: tuple[str, ...]
    #: How long before the run it happened.
    ago: timedelta
    coupon: bool


def buyer_emails() -> list[str]:
    return [BUYER_EMAIL.format(n) for n in range(1, BUYER_COUNT + 1)]


def build_plan(slugs: list[str]) -> list[Purchase]:
    """Who buys what, and how long ago. Pure: the same slugs give the same plan.

    Each buyer places one to three orders of one to three courses, never the
    same course twice. The time is drawn so that sales grow steadily over the
    year -- `1 - sqrt(u)` gives a density rising linearly towards today --
    which is what a young catalogue looks like, and gives the "so với kỳ
    trước" arrows something to say.
    """
    rng = random.Random(RANDOM_SEED)
    catalogue = sorted(slugs)
    plan: list[Purchase] = []

    for email in buyer_emails():
        owned: set[str] = set()
        for _ in range(rng.randint(1, 3)):
            available = [slug for slug in catalogue if slug not in owned]
            if not available:
                break
            picked = rng.sample(available, min(rng.choice((1, 1, 1, 2, 2, 3)), len(available)))
            owned.update(picked)

            days = HISTORY_DAYS * (1 - math.sqrt(rng.random()))
            # Waking hours in Vietnam, give or take: the day part of `ago` is
            # what the chart buckets on, the rest just spreads the minutes.
            ago = timedelta(days=int(days), hours=rng.randint(0, 14), minutes=rng.randint(0, 59))
            plan.append(
                Purchase(
                    email=email,
                    slugs=tuple(sorted(picked)),
                    ago=ago,
                    coupon=rng.random() < COUPON_SHARE,
                )
            )

    # Oldest first, as they would have happened.
    plan.sort(key=lambda purchase: purchase.ago, reverse=True)
    return plan


@dataclass(frozen=True, slots=True)
class Written:
    buyers: int
    orders: int
    lines: int
    revenue: Decimal


async def _buyers(session: AsyncSession) -> dict[str, User]:
    existing = {
        user.email: user
        for user in await session.scalars(select(User).where(User.email.in_(buyer_emails())))
    }
    password_hash = hash_password(BUYER_PASSWORD)
    for number, email in enumerate(buyer_emails(), start=1):
        if email not in existing:
            user = User(
                email=email,
                full_name=f"Người mua {number:02d}",
                password_hash=password_hash,
                role="student",
            )
            session.add(user)
            existing[email] = user
    await session.flush()
    return existing


async def _coupon(session: AsyncSession, now: datetime) -> None:
    present = await session.scalar(select(Coupon.id).where(Coupon.code == COUPON_CODE))
    if present is None:
        session.add(
            Coupon(
                code=COUPON_CODE,
                discount_type="percent",
                value=Decimal("20"),
                scope="site",
                valid_from=now - timedelta(days=HISTORY_DAYS + 30),
            )
        )
        await session.flush()


def _callback(order: Order, paid_at: datetime, number: int) -> dict[str, str]:
    params = {
        "vnp_Amount": str(int(order.total * vnpay.AMOUNT_SCALE)),
        "vnp_BankCode": "NCB",
        "vnp_CardType": "ATM",
        "vnp_OrderInfo": f"Thanh toan don hang {order.code}",
        "vnp_PayDate": paid_at.astimezone(vnpay.VIETNAM).strftime(vnpay.TIME_FORMAT),
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": LOCAL_TMN_CODE,
        "vnp_TransactionNo": f"SEED{number:08d}",
        "vnp_TransactionStatus": "00",
        "vnp_TxnRef": order.code,
    }
    return {**params, "vnp_SecureHash": vnpay.sign(params, LOCAL_SECRET)}


async def seed_sales(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int | None = None,
) -> Written:
    """Make the purchases in the plan -- the first `limit` of them, for a test
    that wants the real path without paying for a hundred checkouts."""
    now = now or datetime.now(UTC)

    already = await session.scalar(
        select(func.count())
        .select_from(Order)
        .join(User, User.id == Order.user_id)
        .where(User.email.in_(buyer_emails()))
    )
    if already:
        return Written(buyers=0, orders=0, lines=0, revenue=Decimal(0))

    courses = {
        course.slug: course
        for course in await session.scalars(
            select(Course).where(
                Course.status == "published", Course.deleted_at.is_(None), Course.price > 0
            )
        )
    }
    if not courses:
        raise SystemExit(
            "Chưa có khóa học có phí nào đang bán. Chạy `python -m scripts.seed` trước."
        )

    buyers = await _buyers(session)
    await _coupon(session, now)
    await session.commit()

    settings = get_settings().model_copy(
        update={"vnpay_tmn_code": LOCAL_TMN_CODE, "vnpay_hash_secret": LOCAL_SECRET}
    )

    orders = lines = 0
    revenue = Decimal(0)
    plan = build_plan(list(courses))[:limit]
    for number, purchase in enumerate(plan, start=1):
        buyer = buyers[purchase.email]
        at = now - purchase.ago
        bought = [courses[slug].id for slug in purchase.slugs]

        for course_id in bought:
            await commerce_service.add_to_cart(session, course_id, buyer)
        view = await orders_service.create_from_cart(
            session, buyer, coupon_code=COUPON_CODE if purchase.coupon else None, now=at
        )
        order = view.order
        answer = await orders_service.handle_vnpay_ipn(
            session, _callback(order, at, number), settings=settings, now=at
        )
        if answer[0] != "00":
            raise SystemExit(f"IPN cho đơn {order.code} bị từ chối: {answer}")

        # The clock, and only the clock -- see the module docstring.
        await session.execute(
            update(Order)
            .where(Order.id == order.id)
            .values(created_at=at - timedelta(minutes=3), updated_at=at)
        )
        await session.execute(
            update(Enrollment)
            .where(Enrollment.user_id == buyer.id, Enrollment.course_id.in_(bought))
            .values(created_at=at, updated_at=at)
        )
        await session.execute(
            update(PaymentEvent).where(PaymentEvent.order_id == order.id).values(created_at=at)
        )
        total = order.total
        await session.commit()

        orders += 1
        lines += len(bought)
        revenue += total

    return Written(buyers=len(buyers), orders=orders, lines=lines, revenue=revenue)


async def purge(session: AsyncSession) -> tuple[int, int]:
    """Remove what this script writes. Returns (buyers, orders).

    Orders go first -- `orders.user_id` is RESTRICT, a paid order is not
    something that disappears with its buyer -- and take their lines and
    events with them. Deleting the buyers then takes their enrolments and
    carts. Every course they had joined gets its student count recounted
    from what is left, the same repair `scripts.rebuild_course_stats` does.
    """
    buyer_ids = select(User.id).where(User.email.in_(buyer_emails()))
    touched = list(
        await session.scalars(
            select(Enrollment.course_id).where(Enrollment.user_id.in_(buyer_ids)).distinct()
        )
    )

    orders = await session.execute(delete(Order).where(Order.user_id.in_(buyer_ids)))
    # `scripts.seed_study` finishes courses for these buyers, and a
    # certificate holds on to its enrolment (RESTRICT).
    await certificates.delete_for_enrollments(
        session, select(Enrollment.id).where(Enrollment.user_id.in_(buyer_ids))
    )
    buyers = await session.execute(delete(User).where(User.email.in_(buyer_emails())))
    await session.execute(delete(Coupon).where(Coupon.code == COUPON_CODE))
    await session.flush()

    if touched:
        await course_stats.rebuild(session, touched)
    await session.flush()
    return buyers.rowcount or 0, orders.rowcount or 0


def _money(amount: Decimal) -> str:
    return f"{int(amount):,}".replace(",", ".")


async def main(purge_first: bool) -> None:
    async with SessionLocal() as session:
        if purge_first:
            buyers, orders = await purge(session)
            await session.commit()
            print(f"Đã gỡ {buyers} người mua và {orders} đơn hàng.")
            return

        written = await seed_sales(session)
        if written.orders == 0:
            print("Dữ liệu bán hàng mẫu đã có sẵn. Chạy với --purge để gỡ rồi nạp lại.")
            return
        print(
            f"Đã nạp {written.orders} đơn hàng ({written.lines} lượt bán) của "
            f"{written.buyers} người mua, tổng {_money(written.revenue)} ₫, trải trong "
            f"{HISTORY_DAYS} ngày gần nhất. Mật khẩu người mua: {BUYER_PASSWORD!r}."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--purge", action="store_true", help="gỡ dữ liệu bán hàng mẫu")
    asyncio.run(main(parser.parse_args().purge))
