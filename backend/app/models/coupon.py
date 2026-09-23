"""Discount codes: how much comes off, what it comes off, and until when.

A coupon is four independent decisions, and keeping them in four columns is
what stops the table from growing a row type per campaign:

* **how much** -- `discount_type` + `value`: a share (`percent`) or an amount
  of VND (`fixed`);
* **what** -- `scope`: everything on sale (`site`), or only the courses named
  in `coupon_courses`;
* **how long** -- `valid_from` .. `valid_to`, the second one nullable for a
  code with no end date;
* **how many times** -- `max_uses`, also nullable for an unlimited one.

`used_count` lives here rather than being counted from `orders` on demand.
Counting would be the more normalised answer and the wrong one: the rule to
enforce is "the hundredth checkout wins and the hundred-and-first does not",
which needs a single row to lock, not an aggregate that two concurrent
checkouts can both read as ninety-nine. The increment is a conditional
`UPDATE ... WHERE used_count < max_uses` in `app/services/coupons.py`, and the
CHECK below is the backstop that makes a lost update impossible to store.

Nothing here records *who* used a code: the design has no redemption table,
because `orders.coupon_id` will answer that question once orders exist, and a
second place to write it is a second place to disagree. Per-person limits
("one use per account") are therefore not expressible yet, and the service
says so where a caller might expect otherwise.

`coupon_courses` is a plain join table, keyed by the pair -- see the note on
its primary key below.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: `percent` takes a share off; `fixed` takes an amount of VND off.
DISCOUNT_TYPES = ("percent", "fixed")

#: `site` applies to whatever is in the cart; `courses` only to the courses
#: listed in `coupon_courses`.
COUPON_SCOPES = ("site", "courses")

#: Long enough for a readable campaign code, short enough to type by hand.
MAX_CODE_LENGTH = 32


class Coupon(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coupons"

    #: Stored exactly as it will be shown, and matched case-insensitively by
    #: the service -- somebody typing `giam50` into a phone means `GIAM50`.
    code: Mapped[str] = mapped_column(String(MAX_CODE_LENGTH), nullable=False)

    discount_type: Mapped[str] = mapped_column(String(10), nullable=False)
    #: A percentage (1..100) or an amount in VND, depending on the type above.
    #: NUMERIC like every other money column: a percentage of a price must not
    #: pick up a float's rounding error on its way to a total.
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    scope: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'site'")
    )

    #: NULL means unlimited. Zero would mean a coupon nobody may use, which is
    #: what deleting it is for, so the CHECK below rules it out.
    max_uses: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    #: NULL means no end date. A campaign that is meant to stop is stopped by
    #: setting this, which is also how a code is withdrawn early -- there is no
    #: `is_active` flag, because two ways to disable the same thing is one way
    #: too many.
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("code", name="uq_coupons_code"),
        # Codes live in one case so that looking one up is an equality on the
        # unique index rather than `upper(code) = ...` over the whole table --
        # and so that `TET2026` and `tet2026` cannot both exist, which the
        # unique constraint alone would happily allow.
        CheckConstraint("code = upper(code)", name="ck_coupons_code_upper"),
        CheckConstraint("length(code) >= 3", name="ck_coupons_code_length"),
        CheckConstraint(
            "discount_type IN ('percent', 'fixed')", name="ck_coupons_discount_type"
        ),
        CheckConstraint("scope IN ('site', 'courses')", name="ck_coupons_scope"),
        CheckConstraint("value > 0", name="ck_coupons_value_positive"),
        # A "120% off" row would hand money back at checkout. The cap belongs
        # here and not only in the service: the admin screens that will write
        # this table are not the only thing that ever will -- a seed script and
        # a psql session are both one typo away from the same row.
        CheckConstraint(
            "discount_type <> 'percent' OR value <= 100",
            name="ck_coupons_percent_range",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_coupons_period"
        ),
        CheckConstraint("max_uses IS NULL OR max_uses > 0", name="ck_coupons_max_uses"),
        CheckConstraint("used_count >= 0", name="ck_coupons_used_count"),
        # The backstop under the conditional UPDATE in the service: if the
        # guard there is ever removed or raced past, the row refuses to store
        # the overspend instead of quietly recording a hundred-and-first use.
        CheckConstraint(
            "max_uses IS NULL OR used_count <= max_uses", name="ck_coupons_uses_left"
        ),
    )

    def __repr__(self) -> str:
        return f"<Coupon {self.code}>"


class CouponCourse(Base):
    """Which courses a `scope='courses'` coupon covers.

    Keyed by the pair, with no `id` of its own -- the deviation from the
    project's UUID-primary-key rule that `docs/database-design.md` specifies
    for this table. The pair *is* the fact; an id would be a second name for
    it, and the unique constraint that would then be needed to stop duplicates
    would do the primary key's job anyway.

    `created_at` only, for the same reason `refresh_tokens` has only one
    timestamp: both columns of this row are its key, so there is nothing an
    `updated_at` could ever describe.
    """

    __tablename__ = "coupon_courses"

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coupons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<CouponCourse {self.coupon_id} -> {self.course_id}>"
