"""In-app notifications: something happened that concerns this person.

**`payload` is a snapshot.** It carries the ids a link needs and the words the
bell shows (the question's title, who answered), copied when the notification
is written. The thread may be edited or deleted afterwards; a notification is a
record that something happened, and it should still read the way it did.
Following its link to a thread that is gone is a 404 the reader can understand.

**`type` is a closed list** (`ck_notifications_type`), one entry per thing the
platform knows how to announce. What a payload holds depends on its type, so a
type nobody renders is a row nobody can read; adding one is a migration on
purpose.

`read_at` NULL means unread. Two indexes, for the two questions asked of the
table: the bell's "how many unread, and which" reads a partial index -- read
notifications are the bulk of the table and the bell never looks at them --
and the notifications page's "all of mine, newest first" reads the full one.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: Somebody else answered a question you asked.
NOTIFICATION_QA_REPLY = "qa_reply"
#: A learner asked a question in a course you teach.
NOTIFICATION_QA_QUESTION = "qa_question"
#: An admin approved the course you sent for review; it is now on sale.
NOTIFICATION_COURSE_APPROVED = "course_approved"
#: An admin sent your course back, with the reason.
NOTIFICATION_COURSE_REJECTED = "course_rejected"
#: An admin took your published course off the platform after a report.
NOTIFICATION_COURSE_TAKEN_DOWN = "course_taken_down"
#: An admin moved you to another instructor tier, with the reason.
NOTIFICATION_INSTRUCTOR_TIER_CHANGED = "instructor_tier_changed"
NOTIFICATION_TYPES = (
    NOTIFICATION_QA_REPLY,
    NOTIFICATION_QA_QUESTION,
    NOTIFICATION_COURSE_APPROVED,
    NOTIFICATION_COURSE_REJECTED,
    NOTIFICATION_COURSE_TAKEN_DOWN,
    NOTIFICATION_INSTRUCTOR_TIER_CHANGED,
)


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in NOTIFICATION_TYPES) + ")",
            name="ck_notifications_type",
        ),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_notifications_payload_object"),
        Index(
            "ix_notifications_user_unread",
            "user_id",
            text("created_at DESC"),
            postgresql_where=text("read_at IS NULL"),
        ),
        Index("ix_notifications_user_created", "user_id", text("created_at DESC")),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.type} for {self.user_id}>"
