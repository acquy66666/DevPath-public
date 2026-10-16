"""allow_orders_settled_without_a_gateway

An order whose total is 0 đ -- a 100 % code, or a free course checked out
through the cart -- is settled at checkout instead of being sent to VNPay,
which cannot charge nothing. It is recorded with `payment_provider = 'none'`
rather than as a VNPay payment no statement would ever show, so
**`ck_orders_provider`** gains `'none'`.

The downgrade refuses while such orders exist: the old constraint cannot be
restored over rows it forbids, and relabelling them `vnpay` would invent
payments. They are paid orders with enrolments behind them, not rows to
delete.

Revision ID: 79240999111f
Revises: abb01d258134
Create Date: 2026-10-16 16:07:21.133833

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '79240999111f'
down_revision: str | None = 'abb01d258134'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PROVIDERS = "payment_provider IN ('vnpay', 'momo')"
NEW_PROVIDERS = "payment_provider IN ('vnpay', 'momo', 'none')"


def upgrade() -> None:
    op.drop_constraint('ck_orders_provider', 'orders', type_='check')
    op.create_check_constraint('ck_orders_provider', 'orders', NEW_PROVIDERS)


def downgrade() -> None:
    settled = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM orders WHERE payment_provider = 'none'")
    )
    if settled:
        raise RuntimeError(
            f"{settled} order(s) were settled at checkout with payment_provider "
            "'none'; the previous constraint cannot hold them, and they are paid "
            "orders, not rows to delete."
        )
    op.drop_constraint('ck_orders_provider', 'orders', type_='check')
    op.create_check_constraint('ck_orders_provider', 'orders', OLD_PROVIDERS)
