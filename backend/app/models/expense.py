"""Platform expenses: what running the platform cost, as an admin records it.

The profit page subtracts these from what the platform kept of each sale. Two
kinds of cost are not rows here, because the system already knows them:
instructors' shares (frozen on each sold line) and the payment gateway's fee
(estimated from what went through the gateway, `PAYMENT_GATEWAY_FEE_RATE`).
Everything else -- the server, storage, the AI API bill, marketing, people --
arrives on an invoice, and an admin types it in against the day it was incurred.

`category` is a closed list so the profit page can put each cost on its own
line; `other` is there for what does not fit, and needs a description anyway.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

EXPENSE_CATEGORIES = (
    "infrastructure",
    "ai_api",
    "payment_fee",
    "marketing",
    "staff",
    "tax",
    "other",
)
EXPENSE_DESCRIPTION_MAX_LENGTH = 200


class PlatformExpense(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "platform_expenses"

    #: The day the cost belongs to, Vietnamese calendar.
    incurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(String(EXPENSE_DESCRIPTION_MAX_LENGTH), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint(
            "category IN (" + ", ".join(f"'{c}'" for c in EXPENSE_CATEGORIES) + ")",
            name="ck_platform_expenses_category",
        ),
        CheckConstraint("amount > 0", name="ck_platform_expenses_amount"),
        CheckConstraint("length(btrim(description)) > 0", name="ck_platform_expenses_description"),
        Index("ix_platform_expenses_incurred_on", "incurred_on"),
    )

    def __repr__(self) -> str:
        return f"<PlatformExpense {self.incurred_on} {self.category} {self.amount}>"
