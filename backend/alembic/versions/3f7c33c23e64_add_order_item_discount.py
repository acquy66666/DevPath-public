"""add_order_item_discount

What the instructor's revenue dashboard needs from the tables it reads.

**`order_items.discount`** — each line's share of `orders.discount`. An order
stores one discount, but its courses can belong to different instructors, and a
coupon limited to one course must not come out of the revenue of the course
next to it. Which lines a coupon covered could be read back from
`coupon_courses` -- except that scope can be edited after the sale, and a
receipt must not change when a campaign does. So the split is frozen at the
moment of sale, like `unit_price`. **`ck_order_items_discount`** (`0 <= discount
<= unit_price`) is the part of the rule a row can check on its own; that the
lines add up to the order's discount spans rows, so it is the service's.

Orders written before this column get their split **here**, by the same rule
the service now uses -- shared by price over the lines the coupon covers (all of
them for a site-wide coupon, or when the coupon has since been deleted or no
longer covers any), rounded down to the đồng with the leftover to the largest
remainders. The rule is copied rather than imported: a migration has to keep
meaning what it meant when it ran, whatever the application code becomes.

Two indexes, each for a query the dashboard makes:

* **`ix_order_items_course_id`** — sales of one instructor's courses.
  `uq_order_items_order_course` leads with `order_id` and cannot serve it.
* **`ix_enrollments_course_created`** (`course_id`, `created_at`) — enrolments
  of one course, by when they happened. `uq_enrollments_user_course` leads with
  `user_id`.

Revision ID: 3f7c33c23e64
Revises: 99c7ba304d8d
Create Date: 2026-09-24 15:09:08.095961

"""
from collections.abc import Sequence
from decimal import ROUND_FLOOR, Decimal

import sqlalchemy as sa
from alembic import op

revision: str = '3f7c33c23e64'
down_revision: str | None = '99c7ba304d8d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZERO = Decimal("0.00")
DONG = Decimal("1")


def _split(discount: Decimal, prices: list[Decimal]) -> list[Decimal]:
    """`app.services.coupons.split_discount` as of this revision."""
    subtotal = sum(prices, ZERO)
    discount = min(discount, subtotal)
    if discount <= ZERO:
        return [ZERO for _ in prices]

    exact = [discount * price / subtotal for price in prices]
    shares = [value.to_integral_value(rounding=ROUND_FLOOR) for value in exact]
    leftover = int(discount - sum(shares, ZERO))
    by_remainder = sorted(
        range(len(prices)), key=lambda index: exact[index] - shares[index], reverse=True
    )
    for index in by_remainder[:leftover]:
        shares[index] += DONG
    return [share.quantize(ZERO) for share in shares]


def _backfill() -> None:
    bind = op.get_bind()
    orders = bind.execute(
        sa.text(
            "SELECT o.id, o.discount, o.coupon_id, c.scope "
            "FROM orders o LEFT JOIN coupons c ON c.id = o.coupon_id "
            "WHERE o.discount > 0"
        )
    ).all()

    for order_id, discount, coupon_id, scope in orders:
        lines = bind.execute(
            sa.text(
                "SELECT id, course_id, unit_price FROM order_items "
                "WHERE order_id = :order_id ORDER BY created_at, id"
            ),
            {"order_id": order_id},
        ).all()

        eligible = lines
        if scope == "courses":
            covered = set(
                bind.execute(
                    sa.text("SELECT course_id FROM coupon_courses WHERE coupon_id = :id"),
                    {"id": coupon_id},
                ).scalars()
            )
            eligible = [line for line in lines if line.course_id in covered] or lines

        shares = _split(discount, [line.unit_price for line in eligible])
        for line, share in zip(eligible, shares, strict=True):
            bind.execute(
                sa.text("UPDATE order_items SET discount = :share WHERE id = :id"),
                {"share": share, "id": line.id},
            )


def upgrade() -> None:
    op.add_column(
        'order_items',
        sa.Column(
            'discount',
            sa.Numeric(precision=12, scale=2),
            server_default=sa.text('0'),
            nullable=False,
        ),
    )
    _backfill()
    # After the backfill, so the constraint is checked against the real split.
    op.create_check_constraint(
        'ck_order_items_discount',
        'order_items',
        'discount >= 0 AND discount <= unit_price',
    )
    op.create_index('ix_order_items_course_id', 'order_items', ['course_id'], unique=False)
    op.create_index(
        'ix_enrollments_course_created', 'enrollments', ['course_id', 'created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_enrollments_course_created', table_name='enrollments')
    op.drop_index('ix_order_items_course_id', table_name='order_items')
    op.drop_constraint('ck_order_items_discount', 'order_items', type_='check')
    op.drop_column('order_items', 'discount')
