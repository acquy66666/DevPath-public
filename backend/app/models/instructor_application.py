"""A learner asking to teach, and the admin's answer.

**Teaching is granted, not taken.** Until November 2026 any account could make
itself an instructor with one click; now a learner sends an application and an
admin decides. `users.role` changes only when an application is approved, in
the same transaction that records the decision and tells the learner.

**One pending application per person** (`uq_instructor_applications_pending`,
partial): pressing "Gửi yêu cầu" twice does not queue two. Once an application
is decided the person may send another -- somebody turned down for a blank
introduction can write one and try again -- and the earlier rows stay, so an
admin reading a new application can see what was said last time.

**A decision is final and complete.** `decided_at` is set exactly when the
status leaves `pending` (`ck_instructor_applications_decided_at`), and a
rejection always carries the reason the learner reads
(`ck_instructor_applications_rejection_reason`), like a rejected course.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

APPLICATION_STATUSES = ("pending", "approved", "rejected")
APPLICATION_MOTIVATION_MAX_LENGTH = 2000
APPLICATION_REASON_MAX_LENGTH = 1000


class InstructorApplication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "instructor_applications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: What the learner wrote about themselves; optional.
    motivation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    # SET NULL: an admin account leaving does not undo what they decided.
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in APPLICATION_STATUSES) + ")",
            name="ck_instructor_applications_status",
        ),
        CheckConstraint(
            "(status = 'pending') = (decided_at IS NULL)",
            name="ck_instructor_applications_decided_at",
        ),
        CheckConstraint(
            "(status = 'rejected') = (rejection_reason IS NOT NULL)",
            name="ck_instructor_applications_rejection_reason",
        ),
        # The admin queue: by status, oldest first.
        Index("ix_instructor_applications_status", "status", "created_at"),
        # "My latest application", and the history beside a new one.
        Index("ix_instructor_applications_user", "user_id", text("created_at DESC")),
        Index(
            "uq_instructor_applications_pending",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<InstructorApplication {self.user_id} {self.status}>"
