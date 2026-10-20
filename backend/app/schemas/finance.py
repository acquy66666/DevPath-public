"""The admin's money pages on the wire: revenue, rankings, tiers, payouts, profit.

Money is `Decimal` and reaches the browser as a string ("280000.00"); rates
are floats in 0..1; times are ISO strings in UTC, dates are Vietnamese
calendar days.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import (
    EXPENSE_CATEGORIES,
    EXPENSE_DESCRIPTION_MAX_LENGTH,
    PAYOUT_NOTE_MAX_LENGTH,
    PAYOUT_REFERENCE_MAX_LENGTH,
    TIER_NAME_MAX_LENGTH,
    TIER_NOTE_MAX_LENGTH,
)
from app.services.finance import FINANCE_GRANULARITIES

FinanceGranularity = Literal[FINANCE_GRANULARITIES]  # type: ignore[valid-type]
ExpenseCategory = Literal[EXPENSE_CATEGORIES]  # type: ignore[valid-type]
PayoutStatus = Literal["draft", "confirmed", "paid", "void"]


def _required_text(value: str, message: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(message)
    return text


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str


class TierBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    rank: int
    share_rate: Decimal


# --- Revenue -------------------------------------------------------------------


class MoneyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    orders: int
    lines: int
    buyers: int
    list_amount: Decimal
    discount: Decimal
    paid: Decimal
    instructor_share: Decimal
    platform_share: Decimal


class MoneyPointOut(MoneyOut):
    #: First moment of the bucket, Vietnamese wall clock, no zone.
    bucket: datetime


class RevenueOut(BaseModel):
    start: date
    end: date
    granularity: FinanceGranularity
    previous_start: date
    previous_end: date
    instructor: PersonOut | None
    totals: MoneyOut
    previous: MoneyOut
    series: list[MoneyPointOut]


class InstructorMoneyOut(MoneyOut):
    instructor: PersonOut
    tier: TierBriefOut
    courses_sold: int
    share_of_paid: float | None


class CourseMoneyOut(MoneyOut):
    course_id: uuid.UUID
    course_title: str
    course_slug: str
    instructor: PersonOut


class RevenueBreakdownOut(BaseModel):
    start: date
    end: date
    instructors: list[InstructorMoneyOut]
    courses: list[CourseMoneyOut]


# --- Rankings ------------------------------------------------------------------


class RankEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    key: str
    label: str
    detail: str | None
    value: Decimal | float | int
    previous: Decimal | float | int | None


class RankingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    group: str
    title: str
    unit: Literal["money", "count", "rating", "rate", "hours"]
    ascending: bool
    note: str | None
    total_entries: int
    entries: list[RankEntryOut]


class ConcentrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    top1: float | None
    top5: float | None
    top10: float | None
    instructors: int


class LeaderboardsOut(BaseModel):
    start: date
    end: date
    previous_start: date
    previous_end: date
    rankings: list[RankingOut]
    concentration: ConcentrationOut


# --- Tiers ---------------------------------------------------------------------


class TierAdminOut(TierBriefOut):
    description: str | None
    min_paid_students: int
    min_revenue_12m: Decimal
    min_rating: Decimal | None
    min_reviews: int
    min_completion_rate: Decimal | None
    min_qa_answer_rate: Decimal | None
    min_published_courses: int
    min_months_active: int
    instructors: int = 0


class TierUpdateIn(BaseModel):
    """Every field optional; null clears the optional thresholds."""

    name: str | None = Field(default=None, min_length=1, max_length=TIER_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=500)
    share_rate: Decimal | None = Field(default=None, gt=0, le=1, decimal_places=4)
    min_paid_students: int | None = Field(default=None, ge=0)
    min_revenue_12m: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    min_rating: Decimal | None = Field(default=None, ge=1, le=5, decimal_places=2)
    min_reviews: int | None = Field(default=None, ge=0)
    min_completion_rate: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=4)
    min_qa_answer_rate: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=4)
    min_published_courses: int | None = Field(default=None, ge=0)
    min_months_active: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _required_text(value, "Tên cấp không được để trống")

    @model_validator(mode="after")
    def required_stay_set(self) -> "TierUpdateIn":
        cleared = [
            name
            for name in self.model_fields_set
            if getattr(self, name) is None and name in TIER_REQUIRED_FIELDS
        ]
        if cleared:
            raise ValueError(f"Không được bỏ trống: {', '.join(sorted(cleared))}")
        return self


#: Fields that may not be cleared with null -- they are NOT NULL in the table.
TIER_REQUIRED_FIELDS = (
    "name",
    "share_rate",
    "min_paid_students",
    "min_revenue_12m",
    "min_reviews",
    "min_published_courses",
    "min_months_active",
)


class CriterionAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    value: str
    threshold: str
    met: bool
    admin_only: bool


class TierCheckOut(BaseModel):
    tier: TierBriefOut
    met: bool
    criteria: list[CriterionAdminOut]


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    paid_students: int
    revenue_12m: Decimal
    reviews: int
    rating_raw: float | None
    rating: float | None
    completion_rate: float | None
    completion_base: int
    qa_questions: int
    qa_answer_rate: float | None
    published_courses: int
    first_published_at: datetime | None
    months_active: int
    removed_courses_90d: int
    locked: bool


class TierChangeOut(BaseModel):
    id: uuid.UUID
    from_tier: TierBriefOut | None
    to_tier: TierBriefOut
    decided_by: PersonOut | None
    note: str
    metrics: dict
    created_at: datetime


class EvaluationOut(BaseModel):
    instructor: PersonOut
    current: TierBriefOut
    suggested: TierBriefOut
    keeps_current: bool
    flags: list[str]
    metrics: MetricsOut
    checks: list[TierCheckOut]
    last_change: TierChangeOut | None


class TierDecisionIn(BaseModel):
    tier_id: uuid.UUID
    note: str = Field(min_length=1, max_length=TIER_NOTE_MAX_LENGTH)

    @field_validator("note")
    @classmethod
    def note_not_blank(cls, value: str) -> str:
        return _required_text(value, "Cần ghi lý do để giảng viên hiểu quyết định")


# --- Payouts -------------------------------------------------------------------


class BalanceOut(BaseModel):
    instructor: PersonOut
    earned_all_time: Decimal
    unbilled: Decimal
    unbilled_lines: int
    oldest_unbilled: datetime | None
    in_draft: Decimal
    confirmed_unpaid: Decimal
    paid_out: Decimal
    tax_withheld: Decimal


class PayoutSettingsOut(BaseModel):
    minimum: Decimal
    pit_rate: Decimal
    pit_threshold: Decimal


class BalancesOut(BaseModel):
    settings: PayoutSettingsOut
    items: list[BalanceOut]


class StatementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    instructor_id: uuid.UUID
    instructor_name: str
    instructor_email: str
    period_start: date
    period_end: date
    status: PayoutStatus
    line_count: int
    gross_amount: Decimal
    instructor_amount: Decimal
    platform_amount: Decimal
    tax_withheld: Decimal
    payable_amount: Decimal
    note: str | None
    created_at: datetime
    confirmed_at: datetime | None
    paid_at: datetime | None
    payment_reference: str | None
    voided_at: datetime | None
    void_reason: str | None


class StatementLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_code: str
    course_id: uuid.UUID
    course_title: str
    paid_at: datetime
    unit_price: Decimal
    discount: Decimal
    net_amount: Decimal
    share_rate: Decimal
    instructor_amount: Decimal


class StatementDetailOut(StatementOut):
    carried_lines: int
    lines: list[StatementLineOut]


class StatementBatchIn(BaseModel):
    #: Any day of the month to bill; the month must be over.
    month: date
    #: Only these instructors; every instructor with something to bill if empty.
    instructor_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)


class SkippedOut(BaseModel):
    instructor: PersonOut
    amount: Decimal
    lines: int


class StatementBatchOut(BaseModel):
    period_start: date
    period_end: date
    created: list[StatementOut]
    skipped: list[SkippedOut]


class WithholdingIn(BaseModel):
    withhold: bool
    note: str | None = Field(default=None, max_length=PAYOUT_NOTE_MAX_LENGTH)


class PaidIn(BaseModel):
    reference: str = Field(min_length=1, max_length=PAYOUT_REFERENCE_MAX_LENGTH)

    @field_validator("reference")
    @classmethod
    def reference_not_blank(cls, value: str) -> str:
        return _required_text(value, "Cần mã giao dịch chuyển khoản")


class VoidIn(BaseModel):
    reason: str = Field(min_length=1, max_length=PAYOUT_NOTE_MAX_LENGTH)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        return _required_text(value, "Cần ghi lý do hủy bảng kê")


# --- Profit --------------------------------------------------------------------


class ProfitColumnOut(BaseModel):
    start: date
    end: date
    list_amount: Decimal
    discount: Decimal
    collected: Decimal
    instructor_share: Decimal
    platform_revenue: Decimal
    gateway_orders: int
    gateway_fee: Decimal
    expenses: dict[str, Decimal]
    operating_expenses: Decimal
    profit_before_tax: Decimal
    tax: Decimal
    retained: Decimal
    take_rate: float | None
    gross_margin: float | None
    net_margin: float | None


class ProfitOut(BaseModel):
    year: int
    granularity: Literal["month", "quarter"]
    columns: list[ProfitColumnOut]
    total: ProfitColumnOut
    fee_rate: Decimal
    fee_source: str
    category_labels: dict[str, str]


class ExpenseOut(BaseModel):
    id: uuid.UUID
    incurred_on: date
    category: ExpenseCategory
    description: str
    amount: Decimal
    created_by: PersonOut | None
    created_at: datetime


class ExpenseIn(BaseModel):
    incurred_on: date
    category: ExpenseCategory
    description: str = Field(min_length=1, max_length=EXPENSE_DESCRIPTION_MAX_LENGTH)
    amount: Decimal = Field(gt=0, le=Decimal("999999999999.99"), decimal_places=2)

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        return _required_text(value, "Cần mô tả khoản chi")


class ExpenseUpdateIn(BaseModel):
    incurred_on: date | None = None
    category: ExpenseCategory | None = None
    description: str | None = Field(
        default=None, min_length=1, max_length=EXPENSE_DESCRIPTION_MAX_LENGTH
    )
    amount: Decimal | None = Field(
        default=None, gt=0, le=Decimal("999999999999.99"), decimal_places=2
    )

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _required_text(value, "Cần mô tả khoản chi")

    @model_validator(mode="after")
    def something_to_change(self) -> "ExpenseUpdateIn":
        if not self.model_fields_set:
            raise ValueError("Không có gì để sửa")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Mọi trường của khoản chi đều bắt buộc")
        return self


class ExpensePageOut(BaseModel):
    items: list[ExpenseOut]
    total: int
    page: int
    page_size: int
    amount: Decimal
