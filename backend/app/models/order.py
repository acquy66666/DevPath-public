"""Orders: what somebody bought, for how much, and what the bank said.

An order is a **receipt**, and that is the whole shape of this file. Every
number a receipt shows is frozen into it at the moment it is written --
`order_items.unit_price`, `subtotal`, `discount`, `total`, `coupon_code` --
because each of those can change afterwards in the table it came from. A course
goes on sale, a campaign is edited, a coupon is deleted; none of that may
change what a person was charged last week, and none of it may make an old
receipt unprintable.

That is also why the foreign keys point the way they do. `user_id` is RESTRICT:
deleting somebody who has paid for something would leave money in the books
with nobody attached to it. `order_items.course_id` is RESTRICT for the same
reason `enrollments.course_id` is -- a course that was sold cannot be deleted
out from under the sale. `coupon_id` is SET NULL, because a campaign really can
be thrown away later and the order must survive it; `coupon_code` is the copy
that survives.

`status` is a small state machine: `pending` -> `paid` or `failed`, plus
`cancelled` for an order abandoned on purpose. Terminal states are terminal:
the IPN handler refuses to move an order that has already reached one, which is
how a retried callback stops being a second enrolment.

**`uq_orders_provider_txn` is the real idempotency guard.** A duplicate IPN is
not a hypothetical -- VNPay retries until it is answered "00" -- and the code
that handles it can be got wrong. A partial unique index over
(`payment_provider`, `provider_txn_id`) cannot: one bank transaction can be
recorded on exactly one order, whatever the handler does. Partial because it is
NULL until an order is actually paid, and NULLs would otherwise not collide but
would carry an index entry each.

`payment_events` is the append-only side of it: every callback that arrives is
written down before anything is decided about it, valid signature or not.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: `pending` is where every order starts; the other three are terminal.
ORDER_STATUSES = ("pending", "paid", "failed", "cancelled")

#: One provider so far. The column exists because `provider_txn_id` is only
#: unique *within* a provider -- MoMo and VNPay may well both call a
#: transaction `1234567`.
PAYMENT_PROVIDERS = ("vnpay", "momo")

#: `DP` + yymmdd + 6 random characters. Short enough to read out loud on the
#: phone, unique enough that nobody has to think about collisions.
ORDER_CODE_LENGTH = 14


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    #: What the buyer sees and what VNPay is told (`vnp_TxnRef`). A column of
    #: its own rather than the primary key: a UUID with dashes is not what a
    #: payment gateway's reference field is for, and it is not something a
    #: person can read back to support over the phone.
    code: Mapped[str] = mapped_column(String(ORDER_CODE_LENGTH), nullable=False)

    #: All three frozen. `subtotal - discount = total` when the row is written;
    #: keeping only the total would make a receipt that cannot show what the
    #: coupon did, and recomputing it later would read a campaign that may have
    #: been edited since.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    coupon_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coupons.id", ondelete="SET NULL")
    )
    #: The code as it was used. `coupon_id` goes NULL if the campaign is ever
    #: deleted; a receipt that then said nothing about the discount on it would
    #: be a receipt that does not add up.
    coupon_code: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )

    payment_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'vnpay'")
    )
    #: The gateway's own transaction id (`vnp_TransactionNo`), NULL until the
    #: money actually moves.
    provider_txn_id: Mapped[str | None] = mapped_column(String(64))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: The gateway's reason for a refusal (`vnp_ResponseCode`), so the result
    #: page can tell "bạn đã hủy" from "thẻ không đủ số dư" instead of showing
    #: one shrug for both.
    failure_code: Mapped[str | None] = mapped_column(String(10))

    __table_args__ = (
        UniqueConstraint("code", name="uq_orders_code"),
        # Partial: `provider_txn_id` is NULL until payment, and a unique index
        # over NULLs would carry an entry per unpaid order while constraining
        # nothing.
        Index(
            "uq_orders_provider_txn",
            "payment_provider",
            "provider_txn_id",
            unique=True,
            postgresql_where=text("provider_txn_id IS NOT NULL"),
        ),
        Index("ix_orders_user_created", "user_id", text("created_at DESC")),
        CheckConstraint(
            "status IN ('pending', 'paid', 'failed', 'cancelled')",
            name="ck_orders_status",
        ),
        CheckConstraint(
            "payment_provider IN ('vnpay', 'momo')", name="ck_orders_provider"
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND total >= 0",
            name="ck_orders_amounts_non_negative",
        ),
        # The receipt has to add up. Written down here because it is the one
        # invariant every screen that shows an order depends on.
        CheckConstraint("total = subtotal - discount", name="ck_orders_total"),
        # A paid order has both of the things being paid produces; an unpaid
        # one has neither. The state and the evidence for it cannot drift.
        CheckConstraint(
            "(status = 'paid') = (paid_at IS NOT NULL AND provider_txn_id IS NOT NULL)",
            name="ck_orders_paid_evidence",
        ),
    )

    def __repr__(self) -> str:
        return f"<Order {self.code} {self.status}>"


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    #: The price at the moment of sale, never read back from `courses.price`.
    #: This is the column the whole "no price in the cart" decision points at.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    __table_args__ = (
        # No quantity, for the same reason the cart has none: a course cannot
        # be owned twice, so a second line would be the same sale twice.
        UniqueConstraint("order_id", "course_id", name="uq_order_items_order_course"),
        CheckConstraint("unit_price >= 0", name="ck_order_items_unit_price"),
    )

    def __repr__(self) -> str:
        return f"<OrderItem {self.course_id} @ {self.unit_price}>"


class PaymentEvent(Base, UUIDPrimaryKeyMixin):
    """One callback from a payment provider, exactly as it arrived.

    **Append-only**: written before the callback is judged, never updated,
    never deleted. It is the only record of what the gateway actually said, and
    the thing to read when an order's state and a bank statement disagree --
    which is the situation where trusting the code's own account of events is
    precisely what you cannot do.

    `signature_valid` is stored rather than recomputed, because the secret may
    be rotated: a row whose signature checked out in September must not start
    reading as a forgery in November.

    `order_id` is nullable, which the design did not originally say. A callback
    naming a reference that matches no order of ours is the one most worth
    keeping -- it is either a bug in our reference handling or somebody probing
    the endpoint -- and a NOT NULL column would mean the only way to store it
    is to not store it.

    No `updated_at`, like `refresh_tokens`: a row that is never updated has
    nothing for it to say.
    """

    __tablename__ = "payment_events"

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    #: The callback's parameters as received, before anything is decided.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_payment_events_order_id", "order_id"),
        CheckConstraint(
            "provider IN ('vnpay', 'momo')", name="ck_payment_events_provider"
        ),
    )

    def __repr__(self) -> str:
        return f"<PaymentEvent {self.provider} valid={self.signature_valid}>"
