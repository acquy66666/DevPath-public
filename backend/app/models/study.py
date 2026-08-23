"""The two things a student leaves behind in a lesson: notes and a bookmark.

Both hang off the **user**, not the enrolment -- deliberately, and differently
from `lesson_progress`. Progress describes one run through a course and is
worth resetting if somebody starts again. A note is something the person wrote;
it belongs to them, and losing it because an enrolment was rebuilt would be
losing their work.

A lesson can hold many notes and at most one bookmark, which is why only one of
the two carries a unique constraint.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Long enough for a paragraph of thought, short enough that the notes list
# stays a list rather than becoming a document.
NOTE_MAX_LENGTH = 2000


class Note(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )

    # The moment in the video the note is about. Zero for a lesson that has no
    # timeline -- an article -- where it simply means "this lesson".
    timestamp_s: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("timestamp_s >= 0", name="ck_notes_timestamp_non_negative"),
        CheckConstraint("length(content) > 0", name="ck_notes_content_not_empty"),
        # Not unique: the whole point is many notes down one lesson. This is
        # the index behind "my notes on this lesson, in order".
        Index("ix_notes_user_lesson", "user_id", "lesson_id"),
    )

    def __repr__(self) -> str:
        return f"<Note {self.lesson_id} @ {self.timestamp_s}s>"


class Bookmark(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A lesson someone wants to find again. It has no body -- it is the flag."""

    __tablename__ = "bookmarks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        # Bookmarking twice is the same bookmark, so the row is the fact and
        # the constraint is what keeps it a fact.
        UniqueConstraint("user_id", "lesson_id", name="uq_bookmarks_user_lesson"),
    )

    def __repr__(self) -> str:
        return f"<Bookmark {self.lesson_id}>"
