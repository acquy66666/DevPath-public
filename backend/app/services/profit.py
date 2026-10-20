"""The profit page: what the platform kept after paying everyone it owes.

Accrual, by the day an order was paid -- not by the day an instructor was
paid out -- and gross, the way Udemy reports: the whole of what buyers paid is
revenue, instructors' shares are a cost.

    GMV (list prices)                       sum of unit_price
  - coupon discounts
  = collected                               sum of orders.total
  - instructors' shares                     frozen on each line
  = platform revenue                        take rate = this / GMV
  - payment gateway fees (estimated)        gateway orders x GATEWAY_FEE_RATE
  - operating expenses                      entered by an admin, by category
  = profit before tax
  - tax                                     entered by an admin
  = retained profit

**The gateway fee is an estimate.** VNPay's real fee is in the merchant
contract; the rate used here is the domestic card / account rate of a public
schedule for merchants accepting through VNPAY (Nam A Bank, 15/06/2026: 0.8 %).
A 0 đ order went through no gateway and costs nothing. When a real statement
arrives, the difference is recorded as an expense of category `payment_fee`.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import status
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import EXPENSE_CATEGORIES, Order, OrderItem, PlatformExpense, User
from app.services import finance
from app.services.stats_calendar import ZERO, add_months, local, money

GATEWAY_FEE_RATE = Decimal("0.008")
GATEWAY_FEE_FIXED = Decimal("0")
GATEWAY_FEE_SOURCE = (
    "Ước tính 0,8% giá trị giao dịch qua VNPay (thẻ/tài khoản nội địa, biểu phí "
    "công khai của Nam A Bank cho đơn vị chấp nhận thanh toán qua VNPAY, 15/06/2026)"
)
PROFIT_GRANULARITIES = ("month", "quarter")
#: Operating costs: every category but tax, which comes after the line.
OPERATING_CATEGORIES = tuple(c for c in EXPENSE_CATEGORIES if c != "tax")
CATEGORY_LABELS = {
    "infrastructure": "Hạ tầng (máy chủ, tên miền, lưu trữ)",
    "ai_api": "API AI (Gemini)",
    "payment_fee": "Phí cổng thanh toán (điều chỉnh thực tế)",
    "marketing": "Marketing",
    "staff": "Nhân sự",
    "tax": "Thuế",
    "other": "Khác",
}


class ExpenseNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "EXPENSE_NOT_FOUND"


# --- The statement -----------------------------------------------------------


@dataclass(slots=True)
class ProfitColumn:
    """One period of the profit and loss statement."""

    start: date
    end: date
    list_amount: Decimal = ZERO
    discount: Decimal = ZERO
    collected: Decimal = ZERO
    instructor_share: Decimal = ZERO
    platform_revenue: Decimal = ZERO
    gateway_orders: int = 0
    gateway_fee: Decimal = ZERO
    expenses: dict[str, Decimal] = field(
        default_factory=lambda: {category: ZERO for category in EXPENSE_CATEGORIES}
    )

    @property
    def operating_expenses(self) -> Decimal:
        return sum((self.expenses[c] for c in OPERATING_CATEGORIES), ZERO)

    @property
    def profit_before_tax(self) -> Decimal:
        return self.platform_revenue - self.gateway_fee - self.operating_expenses

    @property
    def tax(self) -> Decimal:
        return self.expenses["tax"]

    @property
    def retained(self) -> Decimal:
        return self.profit_before_tax - self.tax

    @property
    def take_rate(self) -> float | None:
        return _ratio(self.platform_revenue, self.list_amount)

    @property
    def gross_margin(self) -> float | None:
        return _ratio(self.platform_revenue - self.gateway_fee, self.collected)

    @property
    def net_margin(self) -> float | None:
        return _ratio(self.retained, self.collected)

    def add(self, other: "ProfitColumn") -> None:
        self.list_amount += other.list_amount
        self.discount += other.discount
        self.collected += other.collected
        self.instructor_share += other.instructor_share
        self.platform_revenue += other.platform_revenue
        self.gateway_orders += other.gateway_orders
        self.gateway_fee += other.gateway_fee
        for category in EXPENSE_CATEGORIES:
            self.expenses[category] += other.expenses[category]


def _ratio(part: Decimal, whole: Decimal) -> float | None:
    return round(float(part / whole), 4) if whole else None


@dataclass(frozen=True, slots=True)
class ProfitReport:
    year: int
    granularity: str
    columns: list[ProfitColumn]
    total: ProfitColumn
    fee_rate: Decimal
    fee_source: str


def gateway_fee(total: Decimal) -> Decimal:
    return (
        (total * GATEWAY_FEE_RATE + GATEWAY_FEE_FIXED)
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        .quantize(ZERO)
    )


async def report(session: AsyncSession, year: int, granularity: str = "month") -> ProfitReport:
    step = 1 if granularity == "month" else 3
    columns: list[ProfitColumn] = []
    first = date(year, 1, 1)
    while first.year == year:
        following = add_months(first, step)
        columns.append(ProfitColumn(start=first, end=date.fromordinal(following.toordinal() - 1)))
        first = following

    def column_of(day: date) -> ProfitColumn:
        return columns[(day.month - 1) // step]

    year_start = finance.Range(date(year, 1, 1), date(year, 12, 31), "day")
    start, stop = year_start.bounds()
    paid_day = cast(local(Order.paid_at), Date).label("day")

    for row in await session.execute(
        select(
            paid_day,
            func.coalesce(func.sum(OrderItem.unit_price), 0).label("list_amount"),
            func.coalesce(func.sum(OrderItem.discount), 0).label("discount"),
            func.coalesce(func.sum(finance.PAID), 0).label("paid"),
            func.coalesce(func.sum(finance.INSTRUCTOR_SHARE), 0).label("share"),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status == "paid", Order.paid_at >= start, Order.paid_at < stop)
        .group_by(paid_day)
    ):
        column = column_of(row.day)
        column.list_amount += money(row.list_amount)
        column.discount += money(row.discount)
        column.collected += money(row.paid)
        column.instructor_share += money(row.share)
        column.platform_revenue += money(row.paid - row.share)

    # The fee is per transaction, so it is estimated order by order.
    for day, total in await session.execute(
        select(cast(local(Order.paid_at), Date), Order.total).where(
            Order.status == "paid",
            Order.payment_provider != "none",
            Order.paid_at >= start,
            Order.paid_at < stop,
        )
    ):
        column = column_of(day)
        column.gateway_orders += 1
        column.gateway_fee += gateway_fee(total)

    for day, category, amount in await session.execute(
        select(PlatformExpense.incurred_on, PlatformExpense.category, PlatformExpense.amount).where(
            PlatformExpense.incurred_on >= date(year, 1, 1),
            PlatformExpense.incurred_on <= date(year, 12, 31),
        )
    ):
        column_of(day).expenses[category] += money(amount)

    total = ProfitColumn(start=date(year, 1, 1), end=date(year, 12, 31))
    for column in columns:
        total.add(column)
    return ProfitReport(year, granularity, columns, total, GATEWAY_FEE_RATE, GATEWAY_FEE_SOURCE)


# --- Expenses ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExpenseView:
    expense: PlatformExpense
    created_by: User | None


async def list_expenses(
    session: AsyncSession,
    *,
    year: int | None,
    month: int | None,
    category: str | None,
    page: int,
    page_size: int,
) -> tuple[list[ExpenseView], int, Decimal]:
    """Expenses newest first, the page's slice and the filtered total amount."""
    conditions = []
    if year is not None:
        first = date(year, month or 1, 1)
        last = add_months(first, 1 if month else 12)
        conditions += [PlatformExpense.incurred_on >= first, PlatformExpense.incurred_on < last]
    if category is not None:
        conditions.append(PlatformExpense.category == category)

    count, amount = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(PlatformExpense.amount), 0)).where(
                *conditions
            )
        )
    ).one()
    rows = await session.execute(
        select(PlatformExpense, User)
        .outerjoin(User, User.id == PlatformExpense.created_by)
        .where(*conditions)
        .order_by(
            PlatformExpense.incurred_on.desc(),
            PlatformExpense.created_at.desc(),
            PlatformExpense.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [ExpenseView(expense, user) for expense, user in rows], count, money(amount)


async def create_expense(session: AsyncSession, admin: User, fields: dict[str, Any]) -> ExpenseView:
    expense = PlatformExpense(created_by=admin.id, **fields)
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return ExpenseView(expense, admin)


async def _expense(session: AsyncSession, expense_id: uuid.UUID) -> PlatformExpense:
    expense = await session.get(PlatformExpense, expense_id)
    if expense is None:
        raise ExpenseNotFoundError("Không tìm thấy khoản chi này")
    return expense


async def update_expense(
    session: AsyncSession, expense_id: uuid.UUID, fields: dict[str, Any]
) -> ExpenseView:
    expense = await _expense(session, expense_id)
    for name, value in fields.items():
        setattr(expense, name, value)
    await session.commit()
    await session.refresh(expense)
    creator = await session.get(User, expense.created_by) if expense.created_by else None
    return ExpenseView(expense, creator)


async def delete_expense(session: AsyncSession, expense_id: uuid.UUID) -> None:
    expense = await _expense(session, expense_id)
    await session.delete(expense)
    await session.commit()
