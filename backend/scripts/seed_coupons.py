"""Demo discount codes, including the ones that are supposed to fail.

    python -m scripts.seed_coupons
    python -m scripts.seed_coupons --purge

A working coupon proves one thing. What a demo actually has to show is the
*rules*: that an expired code is refused with its expiry date, that a campaign
that has run out says so, that a code for two Python courses leaves the rest of
the cart at full price. Each of those needs a coupon in a particular state, and
states are exactly what cannot be produced by clicking. So this seeds six codes
covering one working case each and one refusal each.

**Dates are relative to the moment it runs**, never absolute. A seed written
with a fixed end date is a demo that works until it silently does not, on some
morning weeks later, in front of whoever is watching. `CHAOMUNG50` is always
live, `HETHAN` is always a month in the past.

**It writes rows, not service calls** -- unlike `scripts.seed_cart`, which goes
through `app/services/commerce.py` because that is where the cart's rules live.
Coupons have no creation service yet (the admin screens arrive with the admin
task), and the rules that matter here are in the table itself: a percentage
over 100, a code in lower case, an end date before the start, more uses than
the campaign allows -- each one is a CHECK, so a wrong line below stops with a
constraint violation naming it rather than storing something the API would
never have accepted.

**Runs after `scripts.seed`**: the course-scoped coupon names two paid Python
courses, one written by `scripts.seed` and one by `scripts.seed_interactions`.
A named course that is not there is left out of the code, so it also runs on
the four real courses once the synthetic ones are purged -- the catalogue of
the defence, whose home-page banner advertises `CHAOMUNG50`. Idempotent by
code, like the rest of the seed; `--purge` removes exactly these six.
"""

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models import Coupon, CouponCourse, Course


@dataclass(frozen=True, slots=True)
class CouponPlan:
    """One demo code, with its dates written as offsets from "now".

    `starts_in_days` and `ends_in_days` are counted from the moment the script
    runs -- negative for the past. That is what keeps `HETHAN` expired and
    `CHAOMUNG50` live however long after the seed the demo happens.
    """

    code: str
    discount_type: str
    value: Decimal
    #: What this code exists to demonstrate, printed in the closing table.
    shows: str
    scope: str = "site"
    starts_in_days: int = -7
    ends_in_days: int | None = 30
    max_uses: int | None = None
    used_count: int = 0
    #: Only for `scope='courses'`.
    course_slugs: tuple[str, ...] = field(default_factory=tuple)


DEMO_COUPONS: list[CouponPlan] = [
    CouponPlan(
        code="CHAOMUNG50",
        discount_type="percent",
        value=Decimal("50"),
        shows="giảm 50% toàn sàn, còn hạn",
        max_uses=100,
    ),
    CouponPlan(
        code="GIAM100K",
        discount_type="fixed",
        value=Decimal("100000"),
        shows="giảm số tiền cố định, không giới hạn lượt, không có hạn kết thúc",
        ends_in_days=None,
    ),
    CouponPlan(
        code="PYTHON30",
        discount_type="percent",
        value=Decimal("30"),
        shows="chỉ áp cho khóa Python có phí — phần còn lại của giỏ giữ nguyên giá",
        scope="courses",
        max_uses=50,
        course_slugs=(
            "python-nang-cao-decorator-generator-context-manager",
            "cau-truc-du-lieu-va-giai-thuat-voi-python",
        ),
    ),
    CouponPlan(
        code="HETHAN",
        discount_type="percent",
        value=Decimal("40"),
        shows="đã hết hạn — lời từ chối kèm ngày hết hạn",
        starts_in_days=-60,
        ends_in_days=-30,
    ),
    CouponPlan(
        code="SAPCHAY",
        discount_type="percent",
        value=Decimal("25"),
        shows="chưa tới ngày bắt đầu — lời từ chối kèm ngày mở",
        starts_in_days=7,
        ends_in_days=37,
    ),
    CouponPlan(
        code="HETLUOT",
        discount_type="fixed",
        value=Decimal("50000"),
        shows="đã dùng hết lượt (10/10)",
        max_uses=10,
        used_count=10,
    ),
]


@dataclass(frozen=True, slots=True)
class Written:
    coupons: int
    course_links: int
    #: Courses a scoped code names that are not in the catalogue, left out.
    missing: tuple[str, ...] = ()


async def _courses(session: AsyncSession, slugs: set[str]) -> dict[str, Course]:
    if not slugs:
        return {}
    return {
        course.slug: course
        for course in await session.scalars(
            select(Course).where(Course.slug.in_(slugs))
        )
    }


async def seed_coupons(
    session: AsyncSession, plans: list[CouponPlan] = DEMO_COUPONS
) -> Written:
    """Write the codes that are missing. A code already there is left alone.

    A scoped code covers the courses it names that exist; one that would cover
    none is not written, since every cart would refuse it.
    """
    now = datetime.now(UTC)
    wanted = {slug for plan in plans for slug in plan.course_slugs}
    courses = await _courses(session, wanted)
    missing = tuple(sorted(wanted - set(courses)))

    existing = set(
        await session.scalars(
            select(Coupon.code).where(Coupon.code.in_([plan.code for plan in plans]))
        )
    )

    written = 0
    links = 0
    for plan in plans:
        if plan.code in existing:
            continue
        covered = [slug for slug in plan.course_slugs if slug in courses]
        if plan.course_slugs and not covered:
            continue

        coupon = Coupon(
            code=plan.code,
            discount_type=plan.discount_type,
            value=plan.value,
            scope=plan.scope,
            max_uses=plan.max_uses,
            used_count=plan.used_count,
            valid_from=now + timedelta(days=plan.starts_in_days),
            valid_to=(
                None
                if plan.ends_in_days is None
                else now + timedelta(days=plan.ends_in_days)
            ),
        )
        session.add(coupon)
        await session.flush()
        written += 1

        for slug in covered:
            session.add(
                CouponCourse(coupon_id=coupon.id, course_id=courses[slug].id)
            )
            links += 1

    await session.flush()
    return Written(coupons=written, course_links=links, missing=missing)


async def purge(session: AsyncSession, plans: list[CouponPlan] = DEMO_COUPONS) -> int:
    """Remove exactly these codes. `coupon_courses` follows by CASCADE."""
    result = await session.execute(
        delete(Coupon).where(Coupon.code.in_([plan.code for plan in plans]))
    )
    await session.flush()
    return result.rowcount or 0


def _describe(plan: CouponPlan) -> str:
    if plan.discount_type == "percent":
        amount = f"-{int(plan.value)}%"
    else:
        amount = f"-{int(plan.value):,}".replace(",", ".") + " ₫"
    return f"{plan.code:<12} {amount:>12}  {plan.shows}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--purge", action="store_true", help="Xóa đúng sáu mã demo bên dưới."
    )
    args = parser.parse_args()

    async with SessionLocal() as session:
        if args.purge:
            removed = await purge(session)
            await session.commit()
            print(f"Đã xóa {removed} mã giảm giá.")
            return

        written = await seed_coupons(session)
        await session.commit()

    print(f"mã tạo mới     : {written.coupons}")
    print(f"khóa học gắn mã: {written.course_links}")
    if written.missing:
        print(
            "khóa không có trên sàn, bỏ khỏi mã: "
            + ", ".join(written.missing)
            + " (chạy `python -m scripts.seed_interactions` nếu cần)"
        )
    print()
    for plan in DEMO_COUPONS:
        print("  " + _describe(plan))
    print(
        "\nGõ mã ở ô \"Mã giảm giá\" trong trang /gio-hang. "
        "Ba mã cuối là để xem lời từ chối."
    )


if __name__ == "__main__":
    asyncio.run(main())
