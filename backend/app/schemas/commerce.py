"""The cart and the wishlist on the wire."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.courses import CourseCardOut


class CartItemOut(BaseModel):
    """One line of the cart.

    The course comes as the same card the catalogue draws, so the cart page
    needs nothing else to render a row. There is no `id`: every operation on a
    cart line names the course, because that is what the button next to it is
    about, and an item id would be a second name for the same thing.
    """

    course: CourseCardOut
    added_at: datetime
    #: Already owned -- bought or enrolled after this line went in. Drawn
    #: greyed out and left out of `CartOut.total`.
    already_enrolled: bool


class CartOut(BaseModel):
    """The whole cart, which is what every cart endpoint answers with.

    Unpaged, and bounded instead by `MAX_CART_ITEMS`: the total has to cover
    every line, so a page of lines could never carry a trustworthy one.
    """

    items: list[CartItemOut]
    #: VND. What checking out now would cost -- today's prices, owned lines
    #: excluded. `"0.00"` for an empty cart.
    total: Decimal


class WishlistItemOut(BaseModel):
    """One saved course. No price of its own: the card carries it."""

    course: CourseCardOut
    added_at: datetime


class WishlistCourseIdsOut(BaseModel):
    """Which courses the caller has saved, ids only.

    For drawing the heart on catalogue cards the page already has. The same
    shape, and the same reasoning, as `BookmarkedLessonsOut`.
    """

    course_ids: list[uuid.UUID]
