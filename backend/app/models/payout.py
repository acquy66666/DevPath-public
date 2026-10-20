"""Payout statements: what the platform owes an instructor, line by line.

A statement ("bảng kê thanh toán", the check bill an admin hands over) gathers
every sold line of one instructor's courses that is paid and not yet on another
statement, up to the end of the month it is for. Lines from earlier months that
nobody billed are carried into it -- a month nobody made a statement for is
never lost, it is paid with the next one.

**Each sold line is billed at most once.** `uq_payout_statement_lines_order_item`
says so for the database, whatever the code does. Voiding a statement deletes
its lines, which is what frees those sales for the next statement; the header
stays, with the totals it had, so the books still show it existed.

**A line is a copy.** Course title, prices, the share rate the sale was frozen
with, the instructor's amount -- all written when the statement is drawn up, so
a statement printed next year shows the figures that were paid, whatever has
been renamed or repriced since.

Lifecycle: `draft` (drawn up, can be deleted and drawn again) -> `confirmed`
(locked; the figures are final) -> `paid` (the transfer went out, with its
reference). `void` is reachable from draft or confirmed, never from paid --
money that has left is corrected on the next statement, not by pretending.

The arithmetic is written down as CHECKs because every screen and every export
depends on it: gross = instructor + platform, payable = instructor - tax.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

PAYOUT_STATUSES = ("draft", "confirmed", "paid", "void")
#: `BK` + yymm + 6 random characters: "BK2610K7QX2M".
PAYOUT_CODE_LENGTH = 12
PAYOUT_NOTE_MAX_LENGTH = 1000
PAYOUT_REFERENCE_MAX_LENGTH = 100


class PayoutStatement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payout_statements"

    code: Mapped[str] = mapped_column(String(PAYOUT_CODE_LENGTH), nullable=False)
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    #: Who it was made out to, as they were then -- a renamed account does not
    #: change a statement that was already handed over.
    instructor_name: Mapped[str] = mapped_column(String(150), nullable=False)
    instructor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    #: The month the statement is for, both ends inclusive, Vietnamese calendar.
    #: Lines paid before `period_start` and never billed are carried in.
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))

    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    #: What buyers paid for the lines (each `unit_price - discount`).
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    #: The instructor's share of it, summed from the lines.
    instructor_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    #: What the platform keeps from these lines.
    platform_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    #: Personal income tax withheld on the instructor's behalf, if any.
    tax_withheld: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    #: What is actually transferred.
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    note: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    #: The bank transfer's reference, typed in by whoever sent it.
    payment_reference: Mapped[str | None] = mapped_column(String(PAYOUT_REFERENCE_MAX_LENGTH))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("code", name="uq_payout_statements_code"),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'paid', 'void')", name="ck_payout_statements_status"
        ),
        CheckConstraint("period_start <= period_end", name="ck_payout_statements_period"),
        CheckConstraint(
            "line_count >= 0 AND gross_amount >= 0 AND instructor_amount >= 0 "
            "AND platform_amount >= 0 AND tax_withheld >= 0 AND payable_amount >= 0",
            name="ck_payout_statements_amounts_non_negative",
        ),
        CheckConstraint(
            "gross_amount = instructor_amount + platform_amount",
            name="ck_payout_statements_split",
        ),
        CheckConstraint(
            "payable_amount = instructor_amount - tax_withheld",
            name="ck_payout_statements_payable",
        ),
        # The state and the evidence for it cannot drift, as on `orders`.
        # A void statement may or may not have been confirmed first.
        CheckConstraint(
            "(status = 'draft' AND confirmed_at IS NULL) "
            "OR (status IN ('confirmed', 'paid') AND confirmed_at IS NOT NULL) "
            "OR status = 'void'",
            name="ck_payout_statements_confirmed_evidence",
        ),
        CheckConstraint(
            "(status = 'paid') = (paid_at IS NOT NULL)", name="ck_payout_statements_paid_evidence"
        ),
        CheckConstraint(
            "(status = 'void') = (voided_at IS NOT NULL)", name="ck_payout_statements_void_evidence"
        ),
        Index(
            "ix_payout_statements_instructor_period",
            "instructor_id",
            text("period_start DESC"),
        ),
        Index("ix_payout_statements_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<PayoutStatement {self.code} {self.status}>"


class PayoutStatementLine(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "payout_statement_lines"

    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payout_statements.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False
    )

    order_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_title: Mapped[str] = mapped_column(String(200), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    #: `unit_price - discount`: what the buyer paid for this line.
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    share_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    #: `net_amount * share_rate`, rounded *down* to the đồng; the remainder is
    #: the platform's.
    instructor_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("order_item_id", name="uq_payout_statement_lines_order_item"),
        CheckConstraint("net_amount = unit_price - discount", name="ck_payout_statement_lines_net"),
        CheckConstraint(
            "share_rate > 0 AND share_rate <= 1", name="ck_payout_statement_lines_share_rate"
        ),
        CheckConstraint(
            "instructor_amount >= 0 AND instructor_amount <= net_amount",
            name="ck_payout_statement_lines_instructor_amount",
        ),
        Index("ix_payout_statement_lines_statement", "statement_id", "paid_at"),
    )

    def __repr__(self) -> str:
        return f"<PayoutStatementLine {self.order_code} {self.instructor_amount}>"
