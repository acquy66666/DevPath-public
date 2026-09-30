"""The demo discount codes.

This seed exists so that a demo can show the *refusals*, not only a working
code -- so the tests that matter are the ones that check each planted code
really is in the state it advertises. `HETHAN` has to be refused as expired,
`HETLUOT` as out of uses, `PYTHON30` has to leave a non-Python line at full
price. A code that quietly worked when it was meant to fail would turn the one
part of the demo nobody can improvise into a shrug.

The plan is also checked without a database: names, cases, percentages and
course slugs are all knowable from the file, and a typo caught here is caught
before the constraint violation shows up in front of whoever is setting up.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coupon, CouponCourse, Course, User
from app.services import commerce as commerce_service
from app.services import coupons as coupons_service
from scripts.seed import seed_categories
from scripts.seed_coupons import DEMO_COUPONS, purge, seed_coupons
from scripts.seed_courses import COURSES, seed_courses
from scripts.seed_interactions import (
    SYNTHETIC_COURSES,
    build_population,
    seed_interactions,
)
from tests.api.test_commerce import make_user

SEEDED_SLUGS = {course.slug for course in COURSES} | {
    course.slug for course in SYNTHETIC_COURSES
}

PAID_PYTHON_SLUG = "cau-truc-du-lieu-va-giai-thuat-voi-python"  # 499.000, in PYTHON30
FREE_SLUG = "python-co-ban-cho-nguoi-moi-bat-dau"  # 0 ₫, not in PYTHON30


# --- The plan, with no database ---------------------------------------------


def test_every_course_in_the_plan_is_a_course_the_seeds_write() -> None:
    for plan in DEMO_COUPONS:
        for slug in plan.course_slugs:
            assert slug in SEEDED_SLUGS, f"{slug} không do seed nào tạo ra"


def test_no_code_is_planned_twice() -> None:
    codes = [plan.code for plan in DEMO_COUPONS]
    assert len(set(codes)) == len(codes)


def test_every_code_is_in_the_shape_the_table_accepts() -> None:
    """The same four CHECKs, read off the plan instead of off a failed INSERT."""
    for plan in DEMO_COUPONS:
        assert plan.code == plan.code.upper()
        assert len(plan.code) >= 3
        assert plan.value > 0
        if plan.discount_type == "percent":
            assert plan.value <= 100
        if plan.max_uses is not None:
            assert 0 < plan.max_uses
            assert plan.used_count <= plan.max_uses
        if plan.ends_in_days is not None:
            assert plan.ends_in_days > plan.starts_in_days


def test_only_a_course_scoped_code_names_courses() -> None:
    """A site-wide coupon with a course list would apply to everything anyway
    -- the list would be a lie a reader of the table could not detect."""
    for plan in DEMO_COUPONS:
        assert bool(plan.course_slugs) == (plan.scope == "courses")


def test_the_demo_can_show_every_answer_the_page_has() -> None:
    """One code per outcome, or the demo cannot reach that screen at all."""
    assert any(
        plan.scope == "site" and plan.starts_in_days < 0 < (plan.ends_in_days or 1)
        for plan in DEMO_COUPONS
    ), "không có mã nào đang chạy"
    assert any(plan.scope == "courses" for plan in DEMO_COUPONS)
    assert any(
        plan.ends_in_days is not None and plan.ends_in_days < 0
        for plan in DEMO_COUPONS
    ), "không có mã hết hạn"
    assert any(plan.starts_in_days > 0 for plan in DEMO_COUPONS), "không có mã chưa mở"
    assert any(
        plan.max_uses is not None and plan.used_count >= plan.max_uses
        for plan in DEMO_COUPONS
    ), "không có mã hết lượt"
    assert any(plan.ends_in_days is None for plan in DEMO_COUPONS)
    assert any(plan.discount_type == "fixed" for plan in DEMO_COUPONS)
    assert any(plan.discount_type == "percent" for plan in DEMO_COUPONS)


# --- The plan, against a database -------------------------------------------


@pytest.fixture
async def seeded(db_session: AsyncSession) -> None:
    await seed_categories(db_session)
    await seed_courses(db_session)
    await seed_interactions(db_session, build_population())
    # The developer database may hold a committed run of this seed, its dates
    # counted from the day it ran -- and the seed leaves an existing code
    # alone. A week later "SAPCHAY" has opened and "not started yet" is false.
    # Start every test from today's plan; the transaction is rolled back.
    await purge(db_session)
    await db_session.flush()


@pytest.fixture
async def buyer(db_session: AsyncSession, seeded: None) -> User:
    """Somebody with one paid Python course in their cart.

    The course is in `PYTHON30`'s list on purpose: it is what lets the scoped
    coupon and the site-wide one be told apart by their answers.
    """
    student = await make_user(db_session, "student")
    course = await db_session.scalar(
        select(Course).where(Course.slug == PAID_PYTHON_SLUG)
    )
    assert course is not None
    await commerce_service.add_to_cart(db_session, course.id, student)
    return student


async def test_the_seed_plants_every_code_once(
    db_session: AsyncSession, seeded: None
) -> None:
    await seed_coupons(db_session)

    stored = set(
        await db_session.scalars(
            select(Coupon.code).where(
                Coupon.code.in_([plan.code for plan in DEMO_COUPONS])
            )
        )
    )
    assert stored == {plan.code for plan in DEMO_COUPONS}

    links = await db_session.scalars(
        select(Course.slug)
        .join(CouponCourse, CouponCourse.course_id == Course.id)
        .join(Coupon, Coupon.id == CouponCourse.coupon_id)
        .where(Coupon.code == "PYTHON30")
    )
    assert set(links) == {
        "python-nang-cao-decorator-generator-context-manager",
        PAID_PYTHON_SLUG,
    }


async def test_running_it_twice_writes_nothing_the_second_time(
    db_session: AsyncSession, seeded: None
) -> None:
    await seed_coupons(db_session)

    again = await seed_coupons(db_session)

    assert again.coupons == 0
    assert again.course_links == 0


async def test_purge_takes_back_exactly_the_demo_codes(
    db_session: AsyncSession, seeded: None
) -> None:
    """Including the part it must leave alone: a code somebody wrote by hand
    while demonstrating is not this script's to delete."""
    await seed_coupons(db_session)
    db_session.add(
        Coupon(
            code="TUTAO",
            discount_type="fixed",
            value=Decimal("1000"),
            scope="site",
            valid_from=datetime.now(UTC),
        )
    )
    await db_session.flush()

    await purge(db_session)

    # Scoped to the codes this test knows about: the developer database this
    # runs against may already hold a committed run of the seed.
    mine = [plan.code for plan in DEMO_COUPONS] + ["TUTAO"]
    left = set(await db_session.scalars(select(Coupon.code).where(Coupon.code.in_(mine))))
    assert left == {"TUTAO"}


# --- What the planted states actually do ------------------------------------


async def test_the_live_code_halves_the_cart(
    db_session: AsyncSession, buyer: User
) -> None:
    await seed_coupons(db_session)

    discount = await coupons_service.apply_to_cart(db_session, "CHAOMUNG50", buyer)

    assert discount.subtotal == Decimal("499000.00")
    assert discount.discount == Decimal("249500.00")
    assert discount.total == Decimal("249500.00")


async def test_the_scoped_code_leaves_the_rest_of_the_cart_alone(
    db_session: AsyncSession, buyer: User
) -> None:
    """The case the demo is for: two courses in the cart, one of them covered."""
    await seed_coupons(db_session)
    free = await db_session.scalar(select(Course).where(Course.slug == FREE_SLUG))
    assert free is not None
    await commerce_service.add_to_cart(db_session, free.id, buyer)

    discount = await coupons_service.apply_to_cart(db_session, "PYTHON30", buyer)

    # 30% of the Python course only; the other line is not in the coupon.
    assert discount.discount == Decimal("149700.00")
    assert len(discount.course_ids) == 1


async def test_the_expired_code_is_refused_as_expired(
    db_session: AsyncSession, buyer: User
) -> None:
    await seed_coupons(db_session)

    with pytest.raises(coupons_service.CouponExpiredError):
        await coupons_service.apply_to_cart(db_session, "HETHAN", buyer)


async def test_the_unopened_code_is_refused_as_not_started(
    db_session: AsyncSession, buyer: User
) -> None:
    await seed_coupons(db_session)

    with pytest.raises(coupons_service.CouponNotStartedError):
        await coupons_service.apply_to_cart(db_session, "SAPCHAY", buyer)


async def test_the_spent_code_is_refused_as_out_of_uses(
    db_session: AsyncSession, buyer: User
) -> None:
    await seed_coupons(db_session)

    with pytest.raises(coupons_service.CouponExhaustedError):
        await coupons_service.apply_to_cart(db_session, "HETLUOT", buyer)
