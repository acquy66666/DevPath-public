"""The cart and the wishlist.

Every route here answers about the caller and nothing else: none of them takes
a user id, and none of them can be aimed at somebody else's cart. That is why
they are `/cart` and `/wishlist` rather than hanging off `/users/{id}`.

Adding and removing are PUT and DELETE rather than POST: putting a course in a
cart twice leaves the same cart, so the operation is idempotent and should be
spelled that way. The course id lives in the path for the same reason -- the
thing being named is the course, and a request body would only repeat it.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.categories import CategoryOut
from app.schemas.commerce import (
    CartItemOut,
    CartOut,
    WishlistCourseIdsOut,
    WishlistItemOut,
)
from app.schemas.coupons import CartDiscountOut, CouponApplyIn, CouponOut
from app.schemas.courses import CourseCardBase, CourseCardOut, CourseInstructorOut
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import commerce as commerce_service
from app.services import coupons as coupons_service
from app.services.commerce import CartView

router = APIRouter(tags=["commerce"])


def _card(course, instructor, category) -> CourseCardOut:
    """The catalogue card, assembled from the three rows the service joined."""
    return CourseCardOut(
        **CourseCardBase.model_validate(course).model_dump(),
        instructor=CourseInstructorOut.model_validate(instructor),
        category=CategoryOut.model_validate(category),
    )


def _cart_out(view: CartView) -> CartOut:
    return CartOut(
        items=[
            CartItemOut(
                course=_card(line.course, line.instructor, line.category),
                added_at=line.added_at,
                already_enrolled=line.already_enrolled,
            )
            for line in view.lines
        ],
        total=view.total,
    )


# --- Cart ------------------------------------------------------------------


@router.get("/cart", response_model=CartOut)
async def get_cart(current_user: CurrentUser, session: DbSession) -> CartOut:
    """What is in my cart, and what it would cost.

    An account that has never added anything answers `{"items": [], "total":
    "0.00"}` rather than 404: an empty cart is a cart, and the header badge
    should not have to treat "no cart row yet" as a special case.
    """
    return _cart_out(await commerce_service.get_cart(session, current_user))


@router.put("/cart/courses/{course_id}", response_model=CartOut)
async def add_to_cart(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> CartOut:
    """Put a course in my cart, and hand back the cart it is now in.

    Refuses a course that cannot be bought, each with its own code so the page
    can say why: 404 `COURSE_NOT_FOUND` for one not on sale, 409
    `ALREADY_ENROLLED`, 409 `CANNOT_BUY_OWN_COURSE`, 409 `CART_FULL`.

    Answering with the whole cart is what lets one click update the badge, the
    total and the button together without a second request.
    """
    return _cart_out(
        await commerce_service.add_to_cart(session, course_id, current_user)
    )


@router.delete("/cart/courses/{course_id}", response_model=CartOut)
async def remove_from_cart(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> CartOut:
    """Take a course out of my cart, and hand back what is left.

    Removing something that is not in the cart is not an error -- the caller
    asked for a cart without that course and that is what they get.
    """
    return _cart_out(
        await commerce_service.remove_from_cart(session, course_id, current_user)
    )


@router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(current_user: CurrentUser, session: DbSession) -> None:
    """Empty my cart. 204 because there is nothing left to describe."""
    await commerce_service.clear_cart(session, current_user)


@router.post("/cart/coupon", response_model=CartDiscountOut)
async def apply_coupon(
    payload: CouponApplyIn, current_user: CurrentUser, session: DbSession
) -> CartDiscountOut:
    """Try a discount code against my cart and say what it would take off.

    POST, but it writes nothing: the count of uses moves when an order is paid
    for, not when a code is typed, or a limited campaign could be burnt through
    by people opening the cart page. It is a POST rather than a GET so the code
    stays out of the URL -- and therefore out of access logs, browser history
    and `Referer` headers.

    The answer is only true for the cart as it stands. Removing a course
    changes it, and the checkout re-runs the same checks before charging
    anything, so nothing here is a promise about a later payment.

    Refusals, each with its own code so the box under the input can say what to
    do: 404 `COUPON_NOT_FOUND`, 409 `COUPON_NOT_STARTED`, 409 `COUPON_EXPIRED`,
    409 `COUPON_EXHAUSTED`, 409 `COUPON_NOT_APPLICABLE` (live code, none of
    these courses), 409 `CART_EMPTY`.
    """
    discount = await coupons_service.apply_to_cart(
        session, payload.code, current_user
    )

    return CartDiscountOut(
        coupon=CouponOut.model_validate(discount.coupon),
        course_ids=discount.course_ids,
        subtotal=discount.subtotal,
        discount=discount.discount,
        total=discount.total,
    )


# --- Wishlist --------------------------------------------------------------


@router.get("/wishlist", response_model=Page[WishlistItemOut])
async def list_wishlist(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[WishlistItemOut]:
    """"Danh sách yêu thích" — most recently saved first.

    Paged, unlike the cart: nothing bounds how many courses somebody saves.
    """
    rows, total = await commerce_service.list_wishlist(
        session, current_user, page=page, page_size=page_size
    )

    return Page[WishlistItemOut](
        items=[
            WishlistItemOut(
                course=_card(course, instructor, category), added_at=added_at
            )
            for course, instructor, category, added_at in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/wishlist/course-ids", response_model=WishlistCourseIdsOut)
async def list_wishlisted_course_ids(
    current_user: CurrentUser, session: DbSession
) -> WishlistCourseIdsOut:
    """Which courses I have saved — for filling in the heart on a listing."""
    return WishlistCourseIdsOut(
        course_ids=await commerce_service.wishlisted_course_ids(session, current_user)
    )


@router.put(
    "/wishlist/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def add_to_wishlist(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Save a course for later. Saving it twice is saving it once.

    204 rather than the list back: the wishlist is paged, so there is no one
    object to return, and the caller knows what it just saved.
    """
    await commerce_service.add_to_wishlist(session, course_id, current_user)


@router.delete(
    "/wishlist/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_from_wishlist(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Unsave it. Removing one that is not saved is not an error either."""
    await commerce_service.remove_from_wishlist(session, course_id, current_user)
