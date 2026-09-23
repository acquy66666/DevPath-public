"""Carts and wishlists for a few seeded learners, so a demo opens on a full one.

    python -m scripts.seed_cart
    python -m scripts.seed_cart --purge

Everything else about the shop can be demonstrated by clicking: adding a course
takes one button. A *full* cart cannot -- somebody has to have filled it
beforehand, and doing that by hand in front of an examiner is how a demo turns
into a typing exercise. So three learners arrive with a cart and a wishlist
already in them.

**It writes through `app/services/commerce.py`, not through the tables.** The
service is where the rules live -- a course must be on sale, must not be one
the learner already owns, must not be one they teach -- and a seed that wrote
rows directly could put the database in a state the API refuses to create.
Then a demo would show a cart no user could ever have. Going through the same
door as the UI makes that impossible by construction: if a line here is wrong,
this script stops with the same error the button would have shown.

**Runs after `scripts.seed_interactions`.** The learners and most of the priced
courses come from there; the base seed has neither a student account nor more
than one paid course. A missing account or course stops the script with the
command to run first rather than a half-filled cart.

**Idempotent**, like the rest of the seed: a second run adds nothing, because
the service treats adding what is already there as the same intention stated
twice. `--purge` removes exactly the lines named below and nothing else -- a
course somebody added by hand to one of these carts stays.

The three carts are deliberately different, so two demo accounts opened side by
side do not show the same screen; one of them holds a free course, because the
cart accepts those on purpose (a zero total is a case checkout has to handle
once a 100% coupon exists) and a demo that never shows one hides the rule.
"""

import argparse
import asyncio
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.exceptions import DomainError
from app.models import Cart, CartItem, Course, User, Wishlist
from app.services import commerce as commerce_service


@dataclass(frozen=True, slots=True)
class CartPlan:
    """One learner's shop state: what they mean to buy, what they saved.

    Both lists name courses the learner is *not* enrolled in -- see the module
    docstring. The comment beside each slug is its seeded price, so the totals
    printed at the end can be checked against this table by eye.
    """

    email: str
    #: Which interest cluster `scripts.seed_interactions` put them in.
    cluster: str
    cart: tuple[str, ...]
    wishlist: tuple[str, ...]


DEMO_CARTS: list[CartPlan] = [
    CartPlan(
        email="hocvien01@seed.devpath.example",
        cluster="frontend",
        cart=(
            "typescript-cho-nguoi-da-viet-javascript",  # 399.000
            "postgresql-cho-lap-trinh-vien-ung-dung",  # 399.000
            # Free, and in the cart on purpose: the total below stays at
            # 798.000 and the cart page draws a "Miễn phí" line next to two
            # priced ones.
            "html-css-hien-dai-flexbox-grid-va-responsive",  # 0
        ),
        wishlist=(
            "redis-cache-hang-doi-va-gioi-han-truy-cap",
            "quy-hoach-dong-qua-20-bai-toan",
        ),
    ),
    CartPlan(
        email="hocvien13@seed.devpath.example",
        cluster="backend",
        cart=(
            "redis-cache-hang-doi-va-gioi-han-truy-cap",  # 499.000
            "python-nang-cao-decorator-generator-context-manager",  # 499.000
        ),
        wishlist=(
            "nhap-mon-hoc-may-voi-scikit-learn",
            "docker-va-docker-compose-cho-moi-truong-phat-trien",
        ),
    ),
    CartPlan(
        email="hocvien25@seed.devpath.example",
        cluster="python",
        cart=(
            "python-nang-cao-decorator-generator-context-manager",  # 499.000
            "do-thi-va-cac-thuat-toan-duyet",  # 399.000
        ),
        wishlist=(
            "typescript-cho-nguoi-da-viet-javascript",
            # The one paid course the base seed writes, so this line survives
            # `seed_interactions --purge`.
            "cau-truc-du-lieu-va-giai-thuat-voi-python",
        ),
    ),
]


@dataclass(frozen=True, slots=True)
class Written:
    learners: int
    cart_items: int
    wishlist_items: int
    #: Email -> (how many lines, what it would cost), for the closing report.
    totals: dict[str, tuple[int, Decimal]]


def _wanted_slugs(plans: list[CartPlan]) -> set[str]:
    return {slug for plan in plans for slug in (*plan.cart, *plan.wishlist)}


async def _load(
    session: AsyncSession, plans: list[CartPlan]
) -> tuple[dict[str, User], dict[str, Course]]:
    """The learners and courses the plan names, or a message saying what to run.

    Both lookups are by the natural key the plan is written in -- email and
    slug -- so this file stays readable next to `seed_interactions.py`, which
    is written the same way.
    """
    emails = [plan.email for plan in plans]
    learners = {
        user.email: user
        for user in await session.scalars(select(User).where(User.email.in_(emails)))
    }
    missing_learners = sorted(set(emails) - set(learners))
    if missing_learners:
        raise SystemExit(
            "Chưa có các tài khoản học viên: "
            + ", ".join(missing_learners)
            + ". Chạy `python -m scripts.seed_interactions` trước."
        )

    slugs = _wanted_slugs(plans)
    courses = {
        course.slug: course
        for course in await session.scalars(
            select(Course).where(Course.slug.in_(slugs))
        )
    }
    missing_courses = sorted(slugs - set(courses))
    if missing_courses:
        raise SystemExit(
            "Chưa có các khóa học: "
            + ", ".join(missing_courses)
            + ". Chạy `python -m scripts.seed` và `python -m scripts.seed_interactions` "
            "trước."
        )

    return learners, courses


async def seed_carts(
    session: AsyncSession, plans: list[CartPlan] = DEMO_CARTS
) -> Written:
    """Fill the carts and wishlists, skipping whatever is already there.

    Each write goes through the service, so a plan line that breaks one of the
    shop's rules stops the script here, naming the line -- rather than writing
    a row the API would have refused and leaving somebody to find it in a demo.
    """
    learners, courses = await _load(session, plans)

    cart_items = 0
    wishlist_items = 0
    totals: dict[str, tuple[int, Decimal]] = {}

    for plan in plans:
        learner = learners[plan.email]

        for slug in plan.cart:
            course = courses[slug]
            present = await session.scalar(
                select(CartItem.id)
                .join(Cart, Cart.id == CartItem.cart_id)
                .where(Cart.user_id == learner.id, CartItem.course_id == course.id)
            )
            if present is not None:
                continue
            try:
                await commerce_service.add_to_cart(session, course.id, learner)
            except DomainError as refusal:
                raise SystemExit(
                    f"Không thêm được {slug} vào giỏ của {plan.email}: "
                    f"{refusal.message} ({refusal.code}). "
                    "Sửa kế hoạch trong scripts/seed_cart.py."
                ) from refusal
            cart_items += 1

        for slug in plan.wishlist:
            course = courses[slug]
            present = await session.scalar(
                select(Wishlist.id).where(
                    Wishlist.user_id == learner.id, Wishlist.course_id == course.id
                )
            )
            if present is not None:
                continue
            try:
                await commerce_service.add_to_wishlist(session, course.id, learner)
            except DomainError as refusal:
                raise SystemExit(
                    f"Không lưu được {slug} vào yêu thích của {plan.email}: "
                    f"{refusal.message} ({refusal.code}). "
                    "Sửa kế hoạch trong scripts/seed_cart.py."
                ) from refusal
            wishlist_items += 1

        # Read the total back out of the service rather than adding up the
        # comments above: what gets printed is then what the cart page shows.
        view = await commerce_service.get_cart(session, learner)
        totals[plan.email] = (len(view.lines), view.total)

    return Written(
        learners=len(plans),
        cart_items=cart_items,
        wishlist_items=wishlist_items,
        totals=totals,
    )


async def purge(session: AsyncSession, plans: list[CartPlan] = DEMO_CARTS) -> tuple[int, int]:
    """Remove exactly the lines this script writes. Returns (cart, wishlist).

    Named pairs only: somebody may have put a course into one of these carts by
    hand while demonstrating, and taking that out too would be this script
    deciding what a demo meant. Empty cart rows are left behind on purpose --
    an empty cart is what every account starts with anyway.
    """
    learners = {
        user.email: user
        for user in await session.scalars(
            select(User).where(User.email.in_([plan.email for plan in plans]))
        )
    }
    courses = {
        course.slug: course.id
        for course in await session.scalars(
            select(Course).where(Course.slug.in_(_wanted_slugs(plans)))
        )
    }

    cart_removed = 0
    wishlist_removed = 0

    for plan in plans:
        learner = learners.get(plan.email)
        if learner is None:
            continue

        cart_id = await session.scalar(select(Cart.id).where(Cart.user_id == learner.id))
        wanted_cart = [courses[slug] for slug in plan.cart if slug in courses]
        if cart_id is not None and wanted_cart:
            result = await session.execute(
                delete(CartItem).where(
                    CartItem.cart_id == cart_id, CartItem.course_id.in_(wanted_cart)
                )
            )
            cart_removed += result.rowcount or 0

        wanted_wishlist = [courses[slug] for slug in plan.wishlist if slug in courses]
        if wanted_wishlist:
            result = await session.execute(
                delete(Wishlist).where(
                    Wishlist.user_id == learner.id,
                    Wishlist.course_id.in_(wanted_wishlist),
                )
            )
            wishlist_removed += result.rowcount or 0

    await session.flush()
    return cart_removed, wishlist_removed


def _money(amount: Decimal) -> str:
    """198000.00 -> "198.000" -- the thousands separator Vietnamese uses."""
    return f"{int(amount):,}".replace(",", ".")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Xóa đúng những dòng giỏ hàng và yêu thích script này tạo ra.",
    )
    args = parser.parse_args()

    async with SessionLocal() as session:
        if args.purge:
            cart_removed, wishlist_removed = await purge(session)
            await session.commit()
            print(
                f"Đã xóa {cart_removed} dòng giỏ hàng và "
                f"{wishlist_removed} dòng yêu thích."
            )
            return

        written = await seed_carts(session)
        await session.commit()

    print(f"học viên  : {written.learners}")
    print(f"giỏ hàng  : {written.cart_items} dòng tạo mới")
    print(f"yêu thích : {written.wishlist_items} dòng tạo mới")
    for email, (lines, total) in written.totals.items():
        print(f"  {email}: {lines} khóa, {_money(total)} ₫")
    print(
        "\nĐăng nhập bằng mật khẩu học viên seed (SEED_LEARNER_PASSWORD, "
        "mặc định 'devpath-learner') rồi mở /gio-hang."
    )


if __name__ == "__main__":
    asyncio.run(main())
