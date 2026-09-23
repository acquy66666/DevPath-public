"""The demo carts and wishlists.

Seed data that exists for a demo has one job: to be there, correct, and the
same on every machine the morning it is needed. So this file pins the plan
itself -- that every slug in it is a course the seeds really write, and that no
line asks a learner to buy something they already own -- before any of it
reaches a database.

That last one matters more than it looks. `seed_cart` writes through
`app/services/commerce.py`, which refuses a course the learner is enrolled in,
so a wrong line would not corrupt anything: it would stop the script. But it
would stop it in front of whoever is setting up the demo, and the enrolments it
collides with are generated, not written down anywhere a person can read. Here
the collision is caught from the plan alone, with no database and no guessing.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cart, CartItem, Course, User, Wishlist
from app.services import commerce as commerce_service
from scripts.seed import seed_categories
from scripts.seed_cart import DEMO_CARTS, purge, seed_carts
from scripts.seed_courses import COURSES, seed_courses
from scripts.seed_interactions import (
    SYNTHETIC_COURSES,
    build_population,
    seed_interactions,
)

SEEDED_SLUGS = {course.slug for course in COURSES} | {
    course.slug for course in SYNTHETIC_COURSES
}


def test_every_slug_in_the_plan_is_a_course_the_seeds_write() -> None:
    """A typo would otherwise surface as "chưa có khóa học" at demo time."""
    for plan in DEMO_CARTS:
        for slug in (*plan.cart, *plan.wishlist):
            assert slug in SEEDED_SLUGS, f"{slug} không do seed nào tạo ra"


def test_no_line_asks_a_learner_to_buy_what_they_already_have() -> None:
    """The rule the service enforces, checked against the generated history.

    `seed_interactions` decides who is enrolled in what from a fixed seed, so
    this is knowable without a database -- and it is the one way a plan line
    can be wrong while still naming real rows.
    """
    enrolled = {
        learner.email: {item.course_slug for item in learner.items}
        for learner in build_population()
    }

    for plan in DEMO_CARTS:
        assert plan.email in enrolled, f"{plan.email} không nằm trong seed học viên"
        clash = set(plan.cart) & enrolled[plan.email]
        assert not clash, f"{plan.email} đã ghi danh: {sorted(clash)}"


def test_nobody_has_the_same_course_in_both_lists() -> None:
    """Allowed by the API, confusing on a screen: "lưu để sau" next to a line
    already waiting to be paid for says nothing about either."""
    for plan in DEMO_CARTS:
        assert not set(plan.cart) & set(plan.wishlist)


def test_the_three_carts_are_different() -> None:
    """The point of seeding three: two demo accounts opened side by side must
    not show the same screen."""
    carts = [frozenset(plan.cart) for plan in DEMO_CARTS]
    assert len(set(carts)) == len(carts)


def test_one_cart_holds_a_free_course() -> None:
    """The cart takes free courses on purpose -- checkout has to total zero
    once a 100% coupon exists. A demo that never shows one hides the rule."""
    priced = {course.slug: course.price for course in SYNTHETIC_COURSES}
    priced |= {course.slug: course.price for course in COURSES}

    assert any(
        any(priced[slug] == 0 for slug in plan.cart) for plan in DEMO_CARTS
    )


@pytest.fixture
async def seeded(db_session: AsyncSession) -> None:
    await seed_categories(db_session)
    await seed_courses(db_session)
    await seed_interactions(db_session, build_population())
    await db_session.flush()


async def test_the_seed_fills_the_carts_the_page_then_reads(
    db_session: AsyncSession, seeded: None
) -> None:
    """End to end in one rolled-back transaction: write the plan, then read it
    back through the same service `GET /cart` answers from.

    Asserted on the state afterwards, never on how many rows the call created:
    those counters are zero on any machine where the script has already run,
    which is every developer's machine after the first time.
    """
    await seed_carts(db_session)

    learners = {
        user.email: user
        for user in await db_session.scalars(
            select(User).where(User.email.in_([plan.email for plan in DEMO_CARTS]))
        )
    }

    for plan in DEMO_CARTS:
        view = await commerce_service.get_cart(db_session, learners[plan.email])
        assert {line.course.slug for line in view.lines} == set(plan.cart)
        # Nothing is owned yet, so every line counts towards the total.
        assert not any(line.already_enrolled for line in view.lines)
        assert view.total == sum(line.course.price for line in view.lines)

        saved = await db_session.scalars(
            select(Course.slug)
            .join(Wishlist, Wishlist.course_id == Course.id)
            .where(Wishlist.user_id == learners[plan.email].id)
        )
        assert set(saved) == set(plan.wishlist)


async def test_running_it_twice_writes_nothing_the_second_time(
    db_session: AsyncSession, seeded: None
) -> None:
    await seed_carts(db_session)

    again = await seed_carts(db_session)

    assert again.cart_items == 0
    assert again.wishlist_items == 0


async def test_purge_takes_back_exactly_what_it_wrote(
    db_session: AsyncSession, seeded: None
) -> None:
    """Including the part it must leave alone: a course somebody added to one
    of these carts by hand while demonstrating is not this script's to remove.
    """
    await seed_carts(db_session)

    plan = DEMO_CARTS[0]
    learner = await db_session.scalar(select(User).where(User.email == plan.email))
    assert learner is not None
    by_hand = await db_session.scalar(
        select(Course).where(Course.slug == "luyen-phong-van-thuat-toan-trong-30-ngay")
    )
    assert by_hand is not None
    await commerce_service.add_to_cart(db_session, by_hand.id, learner)

    await purge(db_session)

    left = await commerce_service.get_cart(db_session, learner)
    assert [line.course.slug for line in left.lines] == [by_hand.slug]

    emptied = await db_session.scalar(
        select(Wishlist.id).where(Wishlist.user_id == learner.id)
    )
    assert emptied is None


async def test_purge_leaves_the_cart_row_itself(
    db_session: AsyncSession, seeded: None
) -> None:
    """An empty cart is what every account starts with; deleting the row would
    only make the next add create it again."""
    await seed_carts(db_session)
    await purge(db_session)

    learner = await db_session.scalar(
        select(User).where(User.email == DEMO_CARTS[1].email)
    )
    assert learner is not None

    cart_id = await db_session.scalar(select(Cart.id).where(Cart.user_id == learner.id))
    assert cart_id is not None
    assert (
        await db_session.scalar(
            select(CartItem.id).where(CartItem.cart_id == cart_id)
        )
        is None
    )
