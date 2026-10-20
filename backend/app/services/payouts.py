"""Payout statements: drawing up, locking and paying what instructors earned.

**What goes on a statement.** Every sold line of the instructor's courses that
is paid, cost the buyer something (a 0 đ line earns nobody anything), was paid
before the end of the statement's month, and is on no other statement. So a
month nobody billed is carried into the next statement rather than lost -- the
statement says how many of its lines came from before its month.

**When.** Only for a month that is over (Vietnamese calendar): a statement for
the current month would change under the admin's feet. A month's statements
are drawn up in one go for every instructor with something to bill.

**The minimum.** An instructor whose share for the batch is under
`PAYOUT_MINIMUM` is skipped and carried forward -- a transfer has a cost and a
paperwork trail of its own -- except in December, when everything is paid out
so no balance crosses the year (Udemy does the same).

**Tax (an estimate).** Personal income tax is withheld at 10 % when one
payment to an individual reaches 5 000 000 đ (Nghị định 253/2026, in force
from 01/07/2026; 2 000 000 đ before, Thông tư 111/2013). Whether a revenue
share is a fee, business income or a royalty -- and so whether this is the
right rule at all -- is for an accountant; the admin can switch withholding
off on a draft (an instructor who filed form 08/CK-TNCN, for instance). The
statement says it is an estimate.

**Locking.** Lines are copies, written once. Only a draft changes: it can be
deleted, or have its withholding switched. Confirming locks it; paying records
the transfer; voiding (draft or confirmed, never paid) frees its lines for a
later statement and keeps the header with its totals and the reason.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal

from fastapi import status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import (
    Course,
    Order,
    OrderItem,
    PayoutStatement,
    PayoutStatementLine,
    User,
)
from app.services import finance
from app.services.stats_calendar import ZERO, add_months, money
from app.services.vnpay import VIETNAM

PAYOUT_MINIMUM = Decimal("200000.00")
PIT_RATE = Decimal("0.10")
PIT_THRESHOLD = Decimal("5000000.00")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class StatementNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "PAYOUT_STATEMENT_NOT_FOUND"


class StatementStateError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "PAYOUT_STATEMENT_STATE"


class PeriodNotOverError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "PAYOUT_PERIOD_NOT_OVER"


# --- Periods -----------------------------------------------------------------


def month_bounds(month: date) -> tuple[date, date]:
    """First and last day of the month `month` falls in."""
    first = month.replace(day=1)
    return first, add_months(first, 1) - timedelta(days=1)


def _end_of(day: date) -> datetime:
    """The first instant after `day`, Vietnamese calendar."""
    return datetime.combine(day + timedelta(days=1), time(), VIETNAM)


def tax_for(amount: Decimal, *, withhold: bool = True) -> Decimal:
    if not withhold or amount < PIT_THRESHOLD:
        return ZERO
    return (amount * PIT_RATE).quantize(Decimal("1"), rounding=ROUND_DOWN).quantize(ZERO)


# --- Balances ----------------------------------------------------------------


def _billable(until: datetime) -> Select:
    """Sold lines that are paid, cost something, before `until`, and on no
    statement yet."""
    billed = select(PayoutStatementLine.order_item_id)
    return (
        select()
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Course, Course.id == OrderItem.course_id)
        .where(
            Order.status == "paid",
            Order.paid_at < until,
            finance.PAID > 0,
            OrderItem.id.not_in(billed),
        )
    )


@dataclass(frozen=True, slots=True)
class Balance:
    """One instructor's money: earned, on statements by state, and not billed."""

    instructor: User
    earned_all_time: Decimal
    unbilled: Decimal
    unbilled_lines: int
    oldest_unbilled: datetime | None
    in_draft: Decimal
    confirmed_unpaid: Decimal
    paid_out: Decimal
    tax_withheld: Decimal


async def balances(session: AsyncSession, *, now: datetime | None = None) -> list[Balance]:
    """Every instructor who has earned anything, biggest unbilled first."""
    moment = now or datetime.now(UTC)
    earned = dict(
        (
            await session.execute(
                select(Course.instructor_id, func.coalesce(func.sum(finance.INSTRUCTOR_SHARE), 0))
                .select_from(OrderItem)
                .join(Order, Order.id == OrderItem.order_id)
                .join(Course, Course.id == OrderItem.course_id)
                .where(Order.status == "paid")
                .group_by(Course.instructor_id)
            )
        ).all()
    )
    unbilled = {
        row[0]: row[1:]
        for row in await session.execute(
            _billable(moment)
            .add_columns(
                Course.instructor_id,
                func.coalesce(func.sum(finance.INSTRUCTOR_SHARE), 0),
                func.count(),
                func.min(Order.paid_at),
            )
            .group_by(Course.instructor_id)
        )
    }
    by_state: dict[uuid.UUID, dict[str, tuple[Decimal, Decimal]]] = {}
    for instructor_id, state, payable, tax in await session.execute(
        select(
            PayoutStatement.instructor_id,
            PayoutStatement.status,
            func.sum(PayoutStatement.payable_amount),
            func.sum(PayoutStatement.tax_withheld),
        )
        .where(PayoutStatement.status != "void")
        .group_by(PayoutStatement.instructor_id, PayoutStatement.status)
    ):
        by_state.setdefault(instructor_id, {})[state] = (money(payable), money(tax))

    ids = set(earned) | set(by_state)
    users = (
        {user.id: user for user in await session.scalars(select(User).where(User.id.in_(ids)))}
        if ids
        else {}
    )

    result = []
    for instructor_id in ids:
        states = by_state.get(instructor_id, {})
        open_amount, open_lines, oldest = unbilled.get(instructor_id, (0, 0, None))
        result.append(
            Balance(
                instructor=users[instructor_id],
                earned_all_time=money(earned.get(instructor_id)),
                unbilled=money(open_amount),
                unbilled_lines=open_lines,
                oldest_unbilled=oldest,
                in_draft=states.get("draft", (ZERO, ZERO))[0],
                confirmed_unpaid=states.get("confirmed", (ZERO, ZERO))[0],
                paid_out=states.get("paid", (ZERO, ZERO))[0],
                tax_withheld=sum((tax for _, tax in states.values()), ZERO),
            )
        )
    result.sort(key=lambda b: (-b.unbilled, b.instructor.full_name))
    return result


# --- Drawing up --------------------------------------------------------------


def _new_code(month: date) -> str:
    tail = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    return f"BK{month:%y%m}{tail}"


@dataclass(frozen=True, slots=True)
class Skipped:
    instructor: User
    amount: Decimal
    lines: int


@dataclass(frozen=True, slots=True)
class BatchResult:
    period_start: date
    period_end: date
    created: list[PayoutStatement]
    skipped: list[Skipped]


async def create_for_month(
    session: AsyncSession,
    admin: User,
    month: date,
    *,
    instructor_ids: list[uuid.UUID] | None = None,
    now: datetime | None = None,
) -> BatchResult:
    """Draft a statement for every instructor with something to bill up to the
    end of `month` (or only for `instructor_ids`)."""
    moment = now or datetime.now(UTC)
    first, last = month_bounds(month)
    if _end_of(last) > moment:
        raise PeriodNotOverError(
            f"Tháng {first:%m/%Y} chưa kết thúc — chỉ lập bảng kê cho tháng đã qua"
        )
    until = _end_of(last)
    december = first.month == 12

    query = _billable(until).add_columns(
        OrderItem.id,
        OrderItem.course_id,
        OrderItem.unit_price,
        OrderItem.discount,
        OrderItem.instructor_share_rate,
        Order.code,
        Order.paid_at,
        Course.title,
        Course.instructor_id,
    )
    if instructor_ids:
        query = query.where(Course.instructor_id.in_(instructor_ids))
    # Locked so two admins drawing up the same month cannot bill a line twice;
    # the unique index on the lines would stop the second one anyway.
    rows = (
        await session.execute(
            query.order_by(Course.instructor_id, Order.paid_at, Order.code).with_for_update(
                of=OrderItem
            )
        )
    ).all()

    grouped: dict[uuid.UUID, list] = {}
    for row in rows:
        grouped.setdefault(row.instructor_id, []).append(row)

    users = (
        {
            user.id: user
            for user in await session.scalars(select(User).where(User.id.in_(list(grouped))))
        }
        if grouped
        else {}
    )

    created: list[PayoutStatement] = []
    skipped: list[Skipped] = []
    for instructor_id, items in grouped.items():
        user = users[instructor_id]
        lines = []
        for row in items:
            net = money(row.unit_price - row.discount)
            # A paid line always has a rate (`orders._deliver`); the fallback is
            # for nothing but a row written around the service.
            share_rate = row.instructor_share_rate or Decimal("0.5000")
            lines.append(
                PayoutStatementLine(
                    order_item_id=row.id,
                    order_code=row.code,
                    course_id=row.course_id,
                    course_title=row.title,
                    paid_at=row.paid_at,
                    unit_price=money(row.unit_price),
                    discount=money(row.discount),
                    net_amount=net,
                    share_rate=share_rate,
                    instructor_amount=finance.share_of(net, share_rate),
                )
            )
        gross = sum((line.net_amount for line in lines), ZERO)
        share = sum((line.instructor_amount for line in lines), ZERO)
        if share < PAYOUT_MINIMUM and not december:
            skipped.append(Skipped(user, share, len(lines)))
            continue

        tax = tax_for(share)
        statement = PayoutStatement(
            code=_new_code(first),
            instructor_id=user.id,
            instructor_name=user.full_name,
            instructor_email=user.email,
            period_start=first,
            period_end=last,
            status="draft",
            line_count=len(lines),
            gross_amount=gross,
            instructor_amount=share,
            platform_amount=gross - share,
            tax_withheld=tax,
            payable_amount=share - tax,
            created_by=admin.id,
        )
        session.add(statement)
        await session.flush()
        for line in lines:
            line.statement_id = statement.id
        session.add_all(lines)
        created.append(statement)

    await session.commit()
    return BatchResult(first, last, created, skipped)


# --- Reading -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StatementView:
    statement: PayoutStatement
    lines: list[PayoutStatementLine]
    #: Lines paid before the statement's month: carried in from earlier.
    carried_lines: int


async def list_statements(
    session: AsyncSession,
    *,
    status_filter: str | None,
    instructor_id: uuid.UUID | None,
    month: date | None,
    page: int,
    page_size: int,
) -> tuple[list[PayoutStatement], int]:
    query = select(PayoutStatement)
    if status_filter:
        query = query.where(PayoutStatement.status == status_filter)
    if instructor_id:
        query = query.where(PayoutStatement.instructor_id == instructor_id)
    if month:
        query = query.where(PayoutStatement.period_start == month.replace(day=1))
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(
            PayoutStatement.period_start.desc(),
            PayoutStatement.created_at.desc(),
            PayoutStatement.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total or 0


async def _statement(session: AsyncSession, statement_id: uuid.UUID, *, lock: bool = False):
    query = select(PayoutStatement).where(PayoutStatement.id == statement_id)
    if lock:
        query = query.with_for_update()
    statement = await session.scalar(query)
    if statement is None:
        raise StatementNotFoundError("Không tìm thấy bảng kê này")
    return statement


async def get_statement(session: AsyncSession, statement_id: uuid.UUID) -> StatementView:
    statement = await _statement(session, statement_id)
    lines = list(
        await session.scalars(
            select(PayoutStatementLine)
            .where(PayoutStatementLine.statement_id == statement.id)
            .order_by(PayoutStatementLine.paid_at, PayoutStatementLine.order_code)
        )
    )
    period_start = datetime.combine(statement.period_start, time(), VIETNAM)
    carried = sum(1 for line in lines if line.paid_at < period_start)
    return StatementView(statement, lines, carried)


# --- Moving ------------------------------------------------------------------


def _require(statement: PayoutStatement, *allowed: str, action: str) -> None:
    if statement.status not in allowed:
        raise StatementStateError(
            f"Bảng kê {statement.code} đang ở trạng thái “{STATUS_LABELS[statement.status]}”, "
            f"không thể {action}"
        )


STATUS_LABELS = {
    "draft": "Nháp",
    "confirmed": "Đã chốt",
    "paid": "Đã chi trả",
    "void": "Đã hủy",
}


async def set_withholding(
    session: AsyncSession, statement_id: uuid.UUID, withhold: bool, note: str | None
) -> StatementView:
    statement = await _statement(session, statement_id, lock=True)
    _require(statement, "draft", action="sửa")
    statement.tax_withheld = tax_for(statement.instructor_amount, withhold=withhold)
    statement.payable_amount = statement.instructor_amount - statement.tax_withheld
    if note is not None:
        statement.note = note or None
    await session.commit()
    return await get_statement(session, statement_id)


async def confirm(session: AsyncSession, admin: User, statement_id: uuid.UUID) -> StatementView:
    statement = await _statement(session, statement_id, lock=True)
    _require(statement, "draft", action="chốt")
    statement.status = "confirmed"
    statement.confirmed_at = datetime.now(UTC)
    statement.confirmed_by = admin.id
    await session.commit()
    return await get_statement(session, statement_id)


async def mark_paid(
    session: AsyncSession, admin: User, statement_id: uuid.UUID, reference: str
) -> StatementView:
    statement = await _statement(session, statement_id, lock=True)
    _require(statement, "confirmed", action="ghi nhận đã chi trả")
    statement.status = "paid"
    statement.paid_at = datetime.now(UTC)
    statement.paid_by = admin.id
    statement.payment_reference = reference
    await session.commit()
    return await get_statement(session, statement_id)


async def void(session: AsyncSession, statement_id: uuid.UUID, reason: str) -> StatementView:
    """Cancel a statement that was not paid; its lines go back to be billed."""
    statement = await _statement(session, statement_id, lock=True)
    _require(statement, "draft", "confirmed", action="hủy")
    lines = await session.scalars(
        select(PayoutStatementLine).where(PayoutStatementLine.statement_id == statement.id)
    )
    for line in lines:
        await session.delete(line)
    statement.status = "void"
    statement.voided_at = datetime.now(UTC)
    statement.void_reason = reason
    await session.commit()
    return await get_statement(session, statement_id)


async def delete_draft(session: AsyncSession, statement_id: uuid.UUID) -> None:
    statement = await _statement(session, statement_id, lock=True)
    _require(statement, "draft", action="xóa")
    await session.delete(statement)
    await session.commit()
