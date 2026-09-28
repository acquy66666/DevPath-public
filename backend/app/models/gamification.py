"""XP and the daily streak.

`xp_events` is the ledger and the only source of truth for XP: a total is a
sum over it, and the leaderboard is a view of it that can always be rebuilt.
It is **append-only** -- an event is a thing that happened, and un-finishing a
lesson afterwards does not un-happen it.

"The first time" is not a rule the service remembers to check, it is
`uq_xp_events_ref`: one row per (person, reason, thing). Awarding is an insert
that does nothing on conflict, so finishing the same lesson twice, two graders
racing over the same exercise, or a job delivered twice all land on one row.

`streaks` is the other way round: a summary, one row per person, updated in
place. The days it counts are not stored anywhere else, so it cannot be
recomputed from this table -- only from the activity that fed it.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: Why XP was awarded, and what kind of thing `ref_id` then points at. The
#: reason decides the kind: a pair outside this table is a bug, and
#: `ck_xp_events_reason_ref` refuses it.
XP_REASON_REF_TYPES = {
    "lesson_completed": "lesson",
    "quiz_passed": "quiz",
    "exercise_solved": "code_exercise",
}


class XpEvent(Base, UUIDPrimaryKeyMixin):
    """One award of XP, for one action, to one person.

    `ref_id` has no foreign key: it points at a lesson, a quiz or an exercise
    depending on `ref_type`. Deleting the thing afterwards leaves the XP where
    it is -- the student did finish it, and a total that shrank because an
    instructor tidied their course would be a total nobody could trust.

    `amount` is stored rather than looked up from the reason, so changing
    what a reason is worth changes what it is worth *from now on* and leaves
    everybody's history as it was earned.

    No `updated_at`, like `payment_events`: a row that is never updated has
    nothing for it to say.
    """

    __tablename__ = "xp_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    ref_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_xp_events_amount_positive"),
        CheckConstraint(
            " OR ".join(
                f"(reason = '{reason}' AND ref_type = '{ref_type}')"
                for reason, ref_type in XP_REASON_REF_TYPES.items()
            ),
            name="ck_xp_events_reason_ref",
        ),
        # The "first time only" rule. Also serves "everything this person has
        # earned", since it leads with `user_id`.
        UniqueConstraint("user_id", "reason", "ref_type", "ref_id", name="uq_xp_events_ref"),
        # History newest first, and totals over a window (the leaderboard's
        # week and month).
        Index("ix_xp_events_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<XpEvent +{self.amount} {self.reason} {self.ref_id}>"


class Streak(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """How many days in a row somebody has studied, as of the last one.

    The row is created by the first day of activity, so a stored streak is
    never zero. It *reads* as zero once a whole day has gone by without
    activity -- but nothing runs at midnight to write that down: the next
    active day resets it, and until then the service works it out from
    `last_active_date`.

    A day is a day in Vietnam. `last_active_date` is a DATE, not a timestamp,
    because the question it answers is "which calendar day", and a timestamp
    would leave every reader to convert it the same way.
    """

    __tablename__ = "streaks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False)
    last_active_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_streaks_user_id"),
        CheckConstraint(
            "current_streak >= 1 AND longest_streak >= current_streak",
            name="ck_streaks_counts",
        ),
    )

    def __repr__(self) -> str:
        return f"<Streak {self.current_streak}d (best {self.longest_streak}d)>"
