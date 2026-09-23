"""The cart and the wishlist: what somebody means to buy, and what they saved.

Two lists of courses, held to different standards on purpose.

**The cart leads to a payment**, so what goes into it has to be something that
could actually be bought. A course you already own, or one you teach, is
refused at the door -- otherwise the refusal would surface at checkout, after
the person has picked a payment method, which is the worst possible moment to
learn that one line of the order was never payable.

**The wishlist leads nowhere.** It is a bookmark with a price on it. So it
takes anything that is on sale, including courses the person is already
enrolled in: refusing those would buy nothing and would make "save for later"
fail in a way nobody can act on.

Both listings hide courses that are no longer published or have been taken
down. A cart is a claim about what you can buy *now*, and a course withdrawn
from sale yesterday is not that. The rows stay in the table -- they are not
deleted behind the person's back -- they simply stop being shown and stop being
charged for.

A free course is allowed in the cart. It looks pointless, since the enrol
button gives it away for free, but the checkout this feeds has to handle a zero
total anyway (a 100% coupon produces one), and a cart that refuses zero-price
lines would make that path impossible to reach from the UI.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy import Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import (
    MAX_CART_ITEMS,
    Cart,
    CartItem,
    Category,
    Course,
    Enrollment,
    User,
    Wishlist,
)
from app.services import courses as courses_service

ZERO = Decimal("0.00")


class CartFullError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CART_FULL"


class AlreadyEnrolledError(DomainError):
    """You cannot buy a course you are already taking."""

    status_code = status.HTTP_409_CONFLICT
    code = "ALREADY_ENROLLED"


class OwnCourseInCartError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CANNOT_BUY_OWN_COURSE"


class EmptyCartError(DomainError):
    """Nothing in the cart that anybody would be charged for.

    Lives here rather than with the coupon or the order that raise it: both are
    saying the same thing about the same cart, and two codes for it would mean
    two sentences on screen for one situation.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "CART_EMPTY"


@dataclass(frozen=True, slots=True)
class CartLine:
    """One course in the cart, with the two facts the page draws around it."""

    course: Course
    instructor: User
    category: Category
    added_at: datetime
    #: True when the person got the course between adding it and now -- by
    #: enrolling free in another tab, or by a purchase that included it. The
    #: line stays visible, greyed out, and is left out of the total.
    already_enrolled: bool


@dataclass(frozen=True, slots=True)
class CartView:
    """The whole cart. Small by construction, so it is never paged."""

    lines: list[CartLine]
    #: What checking out right now would cost: today's prices, owned lines
    #: excluded. Not a stored number -- see the note on prices in the model.
    total: Decimal


async def _purchasable(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Course:
    """A course that may be put in a list -- on sale, and visible to this person.

    `get_course_for_viewer` already refuses soft-deleted courses and drafts
    belonging to somebody else. The extra check is for the caller's *own*
    draft, which that function lets its owner see: seeing it is fine, buying it
    is not, and the answer is the same 404 everyone else gets rather than a
    different one for the owner.
    """
    course = await courses_service.get_course_for_viewer(session, course_id, user)
    if course.status != "published":
        raise courses_service.CourseNotFoundError("Không tìm thấy khóa học")
    return course


def _listable_courses(item, course_fk) -> Select:
    """The join every listing here shares: item -> course -> its two names.

    Both listings carry `Course.status == 'published'` and the soft-delete
    filter, so a course withdrawn from sale disappears from carts and
    wishlists at the same moment it disappears from the catalogue.
    """
    return (
        select(Course, User, Category)
        .select_from(item)
        .join(Course, Course.id == course_fk)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(Course.deleted_at.is_(None), Course.status == "published")
    )


# --- Cart ------------------------------------------------------------------


async def _find_cart(session: AsyncSession, user: User) -> Cart | None:
    return await session.scalar(select(Cart).where(Cart.user_id == user.id))


async def _get_or_create_cart(session: AsyncSession, user: User) -> Cart:
    """The caller's cart, created on first use.

    `ON CONFLICT DO NOTHING` rather than "look, then insert": two tabs adding a
    course at the same instant would both find no cart, and one of them would
    die on `uq_carts_user_id`.
    """
    await session.execute(
        insert(Cart)
        .values(user_id=user.id)
        .on_conflict_do_nothing(constraint="uq_carts_user_id")
    )
    # `scalar_one`, not `scalar`: after that statement the row exists, whether
    # this transaction wrote it or lost the race to one that did. A cart that
    # is missing here is a broken invariant, not a case to handle.
    return (
        await session.execute(select(Cart).where(Cart.user_id == user.id))
    ).scalar_one()


async def get_cart(session: AsyncSession, user: User) -> CartView:
    """Everything in the caller's cart, newest first, with what it would cost."""
    cart = await _find_cart(session, user)
    if cart is None:
        return CartView(lines=[], total=ZERO)

    listing = (
        _listable_courses(CartItem, CartItem.course_id)
        .add_columns(CartItem.created_at, Enrollment.id)
        # LEFT JOIN: most lines have no enrolment, and the ones that do are the
        # lines the person must not be charged for a second time.
        .outerjoin(
            Enrollment,
            (Enrollment.course_id == CartItem.course_id)
            & (Enrollment.user_id == user.id),
        )
        .where(CartItem.cart_id == cart.id)
        # The id breaks the tie: `created_at` is the transaction's start time,
        # so two courses added together carry the same instant.
        .order_by(CartItem.created_at.desc(), CartItem.id.desc())
    )

    lines = [
        CartLine(
            course=course,
            instructor=instructor,
            category=category,
            added_at=added_at,
            already_enrolled=enrollment_id is not None,
        )
        for course, instructor, category, added_at, enrollment_id in (
            await session.execute(listing)
        ).all()
    ]

    total = sum(
        (line.course.price for line in lines if not line.already_enrolled), ZERO
    )
    return CartView(lines=lines, total=total.quantize(ZERO))


async def add_to_cart(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> CartView:
    """Put a course in the cart. Doing it twice is doing it once.

    Answers with the whole cart rather than the one row: every caller is about
    to redraw a total and a badge, and a second request to fetch what this call
    already knows is a race with itself.
    """
    course = await _purchasable(session, course_id, user)

    if course.instructor_id == user.id:
        raise OwnCourseInCartError("Bạn là giảng viên của khóa học này")

    enrolled = await session.scalar(
        select(Enrollment.id).where(
            Enrollment.user_id == user.id, Enrollment.course_id == course.id
        )
    )
    if enrolled is not None:
        raise AlreadyEnrolledError("Bạn đã có khóa học này")

    cart = await _get_or_create_cart(session, user)

    present = await session.scalar(
        select(CartItem.id).where(
            CartItem.cart_id == cart.id, CartItem.course_id == course.id
        )
    )
    if present is None:
        count = await session.scalar(
            select(func.count()).select_from(CartItem).where(CartItem.cart_id == cart.id)
        )
        if (count or 0) >= MAX_CART_ITEMS:
            raise CartFullError(
                f"Giỏ hàng chỉ chứa tối đa {MAX_CART_ITEMS} khóa học. "
                "Hãy thanh toán bớt hoặc bỏ vài khóa ra rồi thêm tiếp."
            )

        # Two clicks racing each other both pass the check above; the constraint
        # settles it and the loser writes nothing. The cap can therefore be
        # exceeded by one under a genuine race -- it bounds the size of a
        # response, not an invariant anything depends on.
        await session.execute(
            insert(CartItem)
            .values(cart_id=cart.id, course_id=course.id)
            .on_conflict_do_nothing(constraint="uq_cart_items_cart_course")
        )

    await session.commit()
    return await get_cart(session, user)


async def remove_from_cart(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> CartView:
    """Take a course out. Taking out one that is not there is not an error.

    A course the person meanwhile bought, or one that left the catalogue, is
    removed by the same call even though the listing no longer draws it -- the
    delete is by id and does not go through the visibility filter.
    """
    cart = await _find_cart(session, user)
    if cart is not None:
        await session.execute(
            delete(CartItem).where(
                CartItem.cart_id == cart.id, CartItem.course_id == course_id
            )
        )
        await session.commit()

    return await get_cart(session, user)


async def clear_cart(session: AsyncSession, user: User) -> None:
    """Empty the cart, keeping the cart row itself for the next time."""
    cart = await _find_cart(session, user)
    if cart is None:
        return

    await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await session.commit()


# --- Wishlist --------------------------------------------------------------


async def add_to_wishlist(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> None:
    """Save a course for later. Saving it twice is saving it once.

    Unlike the cart this accepts a course you own or teach; see the module
    docstring. The one thing it refuses is a course that is not on sale, which
    `_purchasable` answers as a 404 like everywhere else.
    """
    course = await _purchasable(session, course_id, user)

    await session.execute(
        insert(Wishlist)
        .values(user_id=user.id, course_id=course.id)
        .on_conflict_do_nothing(constraint="uq_wishlists_user_course")
    )
    await session.commit()


async def remove_from_wishlist(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> None:
    """Unsave it. Removing one that is not saved is not an error."""
    await session.execute(
        delete(Wishlist).where(
            Wishlist.user_id == user.id, Wishlist.course_id == course_id
        )
    )
    await session.commit()


async def list_wishlist(
    session: AsyncSession, user: User, *, page: int, page_size: int
) -> tuple[list[tuple[Course, User, Category, datetime]], int]:
    """The caller's saved courses, newest first.

    Paged, unlike the cart: nothing bounds how many courses somebody saves, and
    there is no total to compute that would need every row at once.

    The count is taken through the same joins and filters as the listing, so
    "trang 2 / 7" cannot promise a page that the filter then empties.
    """
    mine = Wishlist.user_id == user.id

    counting = (
        select(func.count())
        .select_from(Wishlist)
        .join(Course, Course.id == Wishlist.course_id)
        .where(mine, Course.deleted_at.is_(None), Course.status == "published")
    )
    total = await session.scalar(counting)

    listing = (
        _listable_courses(Wishlist, Wishlist.course_id)
        .add_columns(Wishlist.created_at)
        .where(mine)
        .order_by(Wishlist.created_at.desc(), Wishlist.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await session.execute(listing)).all()
    return [tuple(row) for row in rows], total or 0


async def wishlisted_course_ids(session: AsyncSession, user: User) -> list[uuid.UUID]:
    """Which courses this person has saved, ids only.

    For the heart on a catalogue card: the page has the courses already and
    only needs to know which ones to fill in. Unfiltered and unpaged on
    purpose -- it is a set membership test, and a course that left the
    catalogue is not on the page to be marked anyway.
    """
    rows = await session.scalars(
        select(Wishlist.course_id).where(Wishlist.user_id == user.id)
    )
    return list(rows)
