"""Who is taking which course.

One row per person per course, which is what `uq_enrollments_user_course`
enforces -- enrolling twice is the same fact stated twice, not two enrolments.

`source` records how the row came to exist. Everything is `free` in Phase 2;
`purchase` arrives with payments in Phase 5, and keeping the column from the
start means the history of who paid for what is not something that has to be
reconstructed later.

The foreign keys point in different directions on purpose. Deleting a user
takes their enrolments with them, because an enrolment describes that person
and nobody else. A course cannot be deleted out from under one -- it is only
ever soft-deleted, so a student who signed up keeps what they signed up for.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ENROLLMENT_SOURCES = ("free", "purchase")


class Enrollment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enrollments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'free'")
    )

    # No status column: a course is finished when every lesson is, and this is
    # where that answer is written down. NULL means still in progress.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "source IN ('free', 'purchase')", name="ck_enrollments_source"
        ),
        UniqueConstraint("user_id", "course_id", name="uq_enrollments_user_course"),
        # "Khóa học của tôi" reads by user and orders by when they signed up.
        Index("ix_enrollments_user_id", "user_id"),
        # The instructor's dashboard reads by course, and by when people joined
        # it. `uq_enrollments_user_course` leads with `user_id`, so it is no help.
        Index("ix_enrollments_course_created", "course_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Enrollment {self.user_id} -> {self.course_id}>"
