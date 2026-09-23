"""The shop side of a course: what you mean to buy, and what you want later.

Three tables, two different shapes, and the difference is the point.

A **cart** is a thing that belongs to a person -- `uq_carts_user_id` says one
each -- and `cart_items` hang off it. The row exists so that checkout has
something to name and lock; it is created the first time somebody puts a course
in it, never in advance, so an account that has only ever taken free courses
carries no cart at all.

A **wishlist** has no owning row. It is not a container, it is a set of facts of
the form "this person wants this course", so it is one flat table keyed by both
-- `uq_wishlists_user_course`. Wrapping it in a parent row would buy nothing
and would need the same lazy-creation dance the cart needs.

Neither table stores a price. `order_items.unit_price` is where a price gets
frozen, at the moment money changes hands; a cart shows today's price because
that is the price you would pay by checking out now. A sale that starts while a
course sits in a cart should lower the total, not be ignored because a number
was copied in last week.

Both foreign keys to `courses` cascade, unlike `enrollments`, whose course key
is RESTRICT. An enrolment is something a student keeps and the course must
survive for; an intention to buy is not. (Courses are soft-deleted in practice,
so what actually keeps a withdrawn course out of a cart is the visibility
filter in `app/services/commerce.py`, not this cascade.)
"""

import uuid

from sqlalchemy import ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: How many courses one cart may hold.
#:
#: The number is not a storage limit -- it is what lets `GET /cart` answer
#: without paging. The total owed has to cover every item, so a paginated cart
#: would have to sum the rows the caller cannot see anyway; bounding the cart
#: is the honest way to keep one response whole. Fifty is far past any real
#: checkout and still small enough to draw in one page.
MAX_CART_ITEMS = 50


class Cart(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("user_id", name="uq_carts_user_id"),)

    def __repr__(self) -> str:
        return f"<Cart of {self.user_id}>"


class CartItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        # The same course twice is the same intention twice, not two purchases.
        # There is no quantity column for the same reason: you cannot own a
        # course twice over.
        UniqueConstraint("cart_id", "course_id", name="uq_cart_items_cart_course"),
        # The cart is read whole, every time, ordered by when things went in.
        Index("ix_cart_items_cart_created", "cart_id", text("created_at DESC")),
    )

    def __repr__(self) -> str:
        return f"<CartItem {self.course_id}>"


class Wishlist(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "wishlists"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_wishlists_user_course"),
        # "Danh sách yêu thích" reads by person, newest first, and pages.
        Index("ix_wishlists_user_created", "user_id", text("created_at DESC")),
    )

    def __repr__(self) -> str:
        return f"<Wishlist {self.user_id} wants {self.course_id}>"
