"""Instructor tiers: the level an instructor has reached, and what it is worth.

**A tier is a share of each sale.** `share_rate` is the instructor's part of
what a buyer paid for one of their courses (`unit_price - discount`); the rest
is the platform's. A higher tier is a bigger share -- that is the whole reward,
and the reason tiers exist.

**The thresholds describe who could be promoted; an admin decides who is.**
`services/instructor_tiers.py` reads the numbers -- paid students, rating,
completion, Q&A answered, months on the platform, and the trailing year's
revenue, which only an admin ever sees -- and names the highest tier whose every
threshold is met. That is a suggestion. The tier an instructor actually has is
`users.instructor_tier_id`, written only by an admin's decision, and every
decision is a row in `instructor_tier_changes` with the numbers it was made on.

**`users.instructor_tier_id` NULL means the first tier** (`rank = 1`). Every
instructor starts there, and the column stays NULL until an admin moves them,
so becoming an instructor -- `POST /users/me/instructor`, an admin changing a
role -- never has to remember to set it.

**A rate is frozen into the sale.** `order_items.instructor_share_rate` is
copied from the instructor's tier when the order is paid. Promoting somebody
in November does not reprice October's sales, and editing a tier's rate here
changes only what is sold from then on.

Five rows, seeded by the migration that created the table; an admin edits
names, rates and thresholds but cannot add or remove tiers -- the ladder is the
product, the numbers on it are policy.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: Ranks run 1..TIER_COUNT, with no gaps; 1 is where everybody starts.
TIER_COUNT = 5
TIER_NAME_MAX_LENGTH = 50
TIER_NOTE_MAX_LENGTH = 1000


class InstructorTier(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "instructor_tiers"

    #: Stable key for code and tests; the name is what people read and may change.
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(TIER_NAME_MAX_LENGTH), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    #: The instructor's share of each sale, 0..1 -- 0.6000 is 60 %.
    share_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    # --- Thresholds: what the numbers must reach to suggest this tier --------
    #: Distinct buyers who paid a real price for one of the instructor's
    #: courses (see `services/instructor_tiers.py`). Admin-only, like revenue:
    #: buyers times the public price is revenue.
    min_paid_students: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    #: What buyers paid for the instructor's courses over the last 365 days.
    #: Admin-only: the instructor sees that the criterion exists, never a number.
    min_revenue_12m: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    #: Bayesian average of buyers' reviews of the instructor's courses; NULL = no bar.
    min_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    #: How many reviews that average must stand on before it counts.
    min_reviews: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    #: Finished enrolments over enrolments, 0..1; NULL = no bar.
    min_completion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    #: Learner questions of the last 90 days answered by the instructor within
    #: 48 hours, 0..1; NULL = no bar. Fewer than 5 questions counts as met.
    min_qa_answer_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    #: Courses on sale now (published, not taken down).
    min_published_courses: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    #: Whole months since the instructor's first course went on sale.
    min_months_active: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_instructor_tiers_code"),
        UniqueConstraint("rank", name="uq_instructor_tiers_rank"),
        CheckConstraint(f"rank BETWEEN 1 AND {TIER_COUNT}", name="ck_instructor_tiers_rank"),
        CheckConstraint(
            "share_rate > 0 AND share_rate <= 1", name="ck_instructor_tiers_share_rate"
        ),
        CheckConstraint(
            "min_paid_students >= 0 AND min_revenue_12m >= 0 AND min_reviews >= 0 "
            "AND min_months_active >= 0 AND min_published_courses >= 0",
            name="ck_instructor_tiers_thresholds_non_negative",
        ),
        CheckConstraint(
            "min_rating IS NULL OR min_rating BETWEEN 1 AND 5",
            name="ck_instructor_tiers_min_rating",
        ),
        CheckConstraint(
            "(min_completion_rate IS NULL OR min_completion_rate BETWEEN 0 AND 1) "
            "AND (min_qa_answer_rate IS NULL OR min_qa_answer_rate BETWEEN 0 AND 1)",
            name="ck_instructor_tiers_rates",
        ),
    )

    def __repr__(self) -> str:
        return f"<InstructorTier {self.rank} {self.code} {self.share_rate}>"


class InstructorTierChange(Base, UUIDPrimaryKeyMixin):
    """One admin decision about one instructor's tier. Append-only.

    `metrics` is what the admin was looking at -- the evaluation as it stood
    when they decided -- so a promotion can be explained later from the row
    alone, after the numbers have moved on. `from_tier_id` NULL is the first
    tier by the same rule as `users.instructor_tier_id`.
    """

    __tablename__ = "instructor_tier_changes"

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    from_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instructor_tiers.id", ondelete="RESTRICT")
    )
    to_tier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instructor_tiers.id", ondelete="RESTRICT"), nullable=False
    )
    #: The admin. SET NULL so an account removed later does not take history with it.
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(btrim(note)) > 0", name="ck_instructor_tier_changes_note"),
        Index(
            "ix_instructor_tier_changes_instructor_created",
            "instructor_id",
            text("created_at DESC"),
        ),
    )

    def __repr__(self) -> str:
        return f"<InstructorTierChange {self.instructor_id} -> {self.to_tier_id}>"
