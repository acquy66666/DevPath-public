"""Somebody flagged something on the platform for an admin to look at.

**`target_id` has no foreign key.** A report points at one of four tables
(`target_type`), and Postgres has no foreign key into "one of four tables". The
cost is accepted: the content may be deleted -- by its author, or by the admin
acting on this very report -- and the report must outlive it, because "what was
reported, and what was done about it" is the record an admin keeps.

**The decision is about the content, not about one reporter.** Resolving or
dismissing a report closes every pending report on the same target in the same
statement, which is why `ix_reports_target` exists. Three people flagging one
review is one decision, not three.

**One pending report per person per target** (`uq_reports_pending_per_reporter`,
partial): pressing "Báo cáo" twice should not queue the same complaint twice,
but a person may report the same thing again once the first report is closed --
content that was left up and then edited into something worse is a new report.

`resolved_at` is set exactly when the report is closed (`ck_reports_closed_at`);
`content_removed` records whether the admin took the content down when
resolving, and only a resolved report can say it did.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

REPORT_TARGET_TYPES = ("course", "review", "qa_thread", "qa_reply")
REPORT_REASONS = ("spam", "offensive", "copyright", "misleading", "other")
REPORT_STATUSES = ("open", "reviewing", "resolved", "dismissed")
#: Waiting for an admin -- the statuses the partial unique index covers.
REPORT_PENDING_STATUSES = ("open", "reviewing")

REPORT_DETAILS_MAX_LENGTH = 1000
REPORT_NOTE_MAX_LENGTH = 1000


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class Report(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reports"

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'open'")
    )
    # SET NULL: an admin account leaving does not reopen what they decided.
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    content_removed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        CheckConstraint(_in("target_type", REPORT_TARGET_TYPES), name="ck_reports_target_type"),
        CheckConstraint(_in("reason", REPORT_REASONS), name="ck_reports_reason"),
        CheckConstraint(_in("status", REPORT_STATUSES), name="ck_reports_status"),
        # "Khác" with nothing written is a report nobody can act on.
        CheckConstraint(
            "reason <> 'other' OR details IS NOT NULL", name="ck_reports_other_has_details"
        ),
        CheckConstraint(
            "(status IN ('resolved', 'dismissed')) = (resolved_at IS NOT NULL)",
            name="ck_reports_closed_at",
        ),
        CheckConstraint(
            "NOT content_removed OR status = 'resolved'",
            name="ck_reports_removed_only_when_resolved",
        ),
        # The admin queue: pending first, oldest first.
        Index("ix_reports_status", "status", "created_at"),
        Index("ix_reports_target", "target_type", "target_id"),
        Index(
            "uq_reports_pending_per_reporter",
            "reporter_id",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'reviewing')"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Report {self.target_type}:{self.target_id} {self.status}>"
