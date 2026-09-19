"""Conversations with the course assistant, kept so they can be read back.

A session is one conversation of one student inside one course. The course is
part of the row, not of each message, because it is what decides which
chunks may be quoted -- a conversation that could drift from one course's
material into another's would be one whose citations stop meaning anything.

Messages are stored **in pairs, after the fact**: the question and the answer
are written together once the answer has finished streaming. A question whose
answer failed halfway is therefore not in the history at all, rather than
sitting there unanswered and being replayed to the model as context on every
later turn. The student sees the failure on screen and can ask again.

Written together, the two rows would share `created_at` if it were left to
the server default -- Postgres's `now()` is the time the *transaction*
started -- and "this session, in order" would put question and answer in
whichever order the planner liked. The service sets both explicitly instead:
the question's to when it arrived, the answer's to when it finished, which is
also simply what those timestamps ought to say.

`cited_lesson_ids` is what the answer actually cited, not what retrieval
offered: the lessons the model pointed at with `[n]`. It is a JSONB array of
UUIDs without foreign keys, like `quiz_attempts.answers` -- a lesson deleted
later leaves a dangling id in an old answer, which the page renders as a
citation that no longer opens, and that is a truer record than rewriting what
the assistant said at the time.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

CHAT_ROLES = ("user", "assistant")

# Long enough to recognise a conversation in a sidebar list, short enough that
# the list does not become the conversation.
CHAT_TITLE_MAX = 120


class ChatSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One student's conversation about one course."""

    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The first question, cut to fit. Null until one has been answered, which
    # the page renders as "cuộc trò chuyện mới".
    title: Mapped[str | None] = mapped_column(String(CHAT_TITLE_MAX))

    __table_args__ = (
        # "My conversations in this course" is the only way sessions are
        # listed, so the index is on the pair rather than on either column.
        Index("ix_chat_sessions_user_course", "user_id", "course_id"),
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.id} user={self.user_id} course={self.course_id}>"


class ChatMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One turn: the student's question or the assistant's answer."""

    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Always an array, empty for a question and for an answer that cited
    # nothing (a refusal) -- never null, so a reader need not ask which.
    cited_lesson_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')", name="ck_chat_messages_role"
        ),
        CheckConstraint(
            "length(content) > 0", name="ck_chat_messages_content_not_empty"
        ),
        CheckConstraint(
            "jsonb_typeof(cited_lesson_ids) = 'array'",
            name="ck_chat_messages_cited_is_array",
        ),
        # Reading a conversation back, and taking its last few turns as the
        # model's context, are both "this session, in order".
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage {self.role} in {self.session_id}>"
