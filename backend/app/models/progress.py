"""How far through a lesson somebody is.

One row per (enrolment, lesson), which is what
`uq_lesson_progress_enrollment_lesson` enforces: progress is a position, and a
position cannot be in two places.

The row hangs off the enrolment rather than off the user, because that is what
progress belongs to -- leave a course and rejoin it and you start again, which
is also what makes the `ON DELETE CASCADE` below correct.

`last_position_s` is where the player should pick up. It is written by a
heartbeat every few seconds, so it is the most frequently updated column in the
schema and deliberately the cheapest: one integer, no history.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LessonProgress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_progress"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )

    last_position_s: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "last_position_s >= 0", name="ck_lesson_progress_position_non_negative"
        ),
        # Also the index for "everything this enrolment has watched": its
        # leading column is `enrollment_id`, so a separate index on that column
        # alone would be a second copy of the same thing.
        UniqueConstraint(
            "enrollment_id",
            "lesson_id",
            name="uq_lesson_progress_enrollment_lesson",
        ),
    )

    def __repr__(self) -> str:
        return f"<LessonProgress {self.lesson_id} @ {self.last_position_s}s>"
