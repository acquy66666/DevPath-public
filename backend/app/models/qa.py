"""Questions and answers under a lesson.

A **thread** is one question somebody asked about one lesson; **replies** are
the answers, in the order they were written; a **vote** is somebody else saying
"I have this question too".

**A vote is a row, not a number.** The plan asks for upvotes only, so there is
no `value` column: a column that could only ever hold 1 would be a second way of
writing the same fact, and the only one of the two that can drift. Counting the
rows is the score; `uq_qa_votes_thread_user` is what keeps it one per person --
the same shape as a bookmark.

**`is_instructor_reply` is decided when the reply is written** and never looked
up again: the badge says who was answering *for the course* at the time. A
course that changes hands later does not rewrite who answered what.

Everything hangs off the lesson and the author with CASCADE: a question about a
lesson that no longer exists has nothing left to be about.
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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

QA_TITLE_MAX_LENGTH = 200
# Room for a question with the code it is about pasted underneath, and not
# much more: an answer that needs more than this is a lesson of its own.
QA_BODY_MAX_LENGTH = 5000


class QaThread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "qa_threads"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(QA_TITLE_MAX_LENGTH), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: When the asker (or the course's instructor) said it was answered.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("length(title) > 0", name="ck_qa_threads_title_not_empty"),
        CheckConstraint("length(body) > 0", name="ck_qa_threads_body_not_empty"),
        # "This lesson's questions, newest first" -- the filter and the order
        # of the list in one B-tree.
        Index("ix_qa_threads_lesson_created", "lesson_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<QaThread {self.title!r}>"


class QaReply(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "qa_replies"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qa_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_instructor_reply: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        CheckConstraint("length(body) > 0", name="ck_qa_replies_body_not_empty"),
        # The replies of one thread in the order they were written, and the
        # per-thread count and "has the instructor answered" of the list.
        Index("ix_qa_replies_thread_created", "thread_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<QaReply on {self.thread_id}>"


class QaVote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Somebody who has the same question. It has no body -- it is the flag."""

    __tablename__ = "qa_votes"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qa_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        # Leads with `thread_id`, so it is also the index the vote count reads.
        UniqueConstraint("thread_id", "user_id", name="uq_qa_votes_thread_user"),
    )

    def __repr__(self) -> str:
        return f"<QaVote on {self.thread_id}>"
