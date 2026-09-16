"""Quizzes, the questions in them, and what happened when someone sat one.

Three tables, and two rules worth stating before the columns.

**The clock belongs to the server.** An attempt's deadline is
`started_at + time_limit_s`, and both halves are read from this row -- never
from anything the browser reports. The countdown a student watches is a
courtesy; the only number that decides whether an answer arrived in time is
computed from these two columns. It is also why `time_limit_s` is copied onto
the attempt instead of joined from the quiz: an instructor editing the quiz
while somebody is sitting it must not move that person's deadline.

**The answer key is not part of the question a student is shown.**
`correct_index` and `explanation` sit on the same row as the question text,
and what keeps them off the wire is that `app/schemas/quiz.py` has a second
model with no field they could travel in -- the same arrangement that keeps a
hidden test case's expected output off a code exercise page.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# How many choices a question may offer. Two is the floor because one option
# is not a question; six is a ceiling rather than a rule of pedagogy -- it is
# what a phone screen shows without scrolling, and it bounds what the quiz
# generator of the next task is allowed to produce.
MIN_OPTIONS = 2
MAX_OPTIONS = 6

# The clock an instructor may set. Below half a minute nobody finishes a
# question; above two hours the "attempt in progress" row stops being a quiz
# and becomes an abandoned tab holding a lock.
MIN_TIME_LIMIT_S = 30
MAX_TIME_LIMIT_S = 7200

DEFAULT_PASS_SCORE = 70


class Quiz(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The quiz behind one `quiz` lesson.

    One per lesson, enforced by a constraint rather than by whoever inserts:
    the lesson is what a student opens, and two quizzes behind it would make
    "the quiz" ambiguous in every query downstream.

    `is_published` is the gate the next task needs: questions written by
    Gemini land here with `ai_generated = true` and `is_published = false`,
    and stay invisible until an instructor has read every one of them. A quiz
    with no questions cannot be published at all -- that rule lives in the
    service, because it is a statement about rows in another table.
    """

    __tablename__ = "quizzes"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )

    # NULL means no clock. An untimed quiz is a legitimate teaching choice --
    # a self-check at the end of a chapter -- and encoding it as NULL keeps
    # "no limit" from being spelled as some large number that later reads like
    # a mistake.
    time_limit_s: Mapped[int | None] = mapped_column(Integer)
    pass_score: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_PASS_SCORE))
    )

    # Whether a model wrote these questions. Kept because "the AI generated
    # this" is a fact about provenance that an instructor, and the thesis,
    # will both want to ask about later -- and it cannot be recovered after
    # the fact from the text.
    ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        UniqueConstraint("lesson_id", name="uq_quizzes_lesson"),
        CheckConstraint("pass_score BETWEEN 0 AND 100", name="ck_quizzes_pass_score"),
        CheckConstraint(
            f"time_limit_s IS NULL OR time_limit_s BETWEEN "
            f"{MIN_TIME_LIMIT_S} AND {MAX_TIME_LIMIT_S}",
            name="ck_quizzes_time_limit",
        ),
    )

    def __repr__(self) -> str:
        return f"<Quiz lesson={self.lesson_id} {'published' if self.is_published else 'draft'}>"


class QuizQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One multiple-choice question: the text, the choices, and which one wins.

    `options` is a JSONB array of strings and `correct_index` points into it.
    The alternative -- a row per choice with an `is_correct` flag -- buys
    ordering and constraints that this design gets from the array itself, and
    costs a join on every render plus a state where a question has no correct
    answer at all.

    That last risk is what the check constraint is for. The design document
    left "correct_index < len(options)" to the service; it is written into the
    table instead, because the service is not the only thing that will insert
    here. The quiz generator of the next task writes rows straight from a
    model's JSON output, and a question whose correct answer points past the
    end of its own choices is unanswerable -- a defect that surfaces as a
    student's wrong mark rather than as an error.
    """

    __tablename__ = "quiz_questions"

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Why that answer is the right one. Shown after an attempt is submitted
    # and never before -- "xem giải thích" is the point of the feature, and
    # reading it mid-attempt is the point of cheating.
    explanation: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # Deferrable for the reason the curriculum's is: renumbering rewrites
        # several rows in one transaction and passes through states where two
        # of them briefly claim the same slot.
        UniqueConstraint(
            "quiz_id",
            "position",
            name="uq_quiz_questions_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        # CASE rather than a chain of ANDs: `jsonb_array_length` raises on a
        # value that is not an array instead of returning false, and Postgres
        # does not promise to evaluate the conjuncts left to right. CASE does
        # promise it, so a malformed `options` is refused by this constraint
        # rather than by a type error from inside it.
        CheckConstraint(
            "CASE WHEN jsonb_typeof(options) = 'array' THEN "
            f"jsonb_array_length(options) BETWEEN {MIN_OPTIONS} AND {MAX_OPTIONS} "
            "AND correct_index >= 0 "
            "AND correct_index < jsonb_array_length(options) "
            "ELSE false END",
            name="ck_quiz_questions_options",
        ),
        CheckConstraint("length(question) > 0", name="ck_quiz_questions_not_empty"),
    )

    def __repr__(self) -> str:
        return f"<QuizQuestion {self.position} of {self.quiz_id}>"


class QuizAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One sitting: when it started, what was answered, what it scored.

    A row is created the moment a student opens the quiz, with `started_at`
    written by the database and `submitted_at`, `answers` and `score` all
    empty. That is the shape of an attempt in progress, and the partial unique
    index below is what makes it mean something: one person can have exactly
    one unfinished attempt at one quiz. Without it, opening the quiz in four
    tabs would start four clocks and let the student keep whichever finished
    best.

    `answers` is written once, at submit, as a JSONB array parallel to the
    questions -- the chosen index per question, or null where nothing was
    chosen. Nothing is saved while the attempt is running, which is a real
    trade-off and is recorded as one: it keeps the table free of write traffic
    per keystroke, and it means a student who runs out of time without
    pressing submit has nothing to be marked on.
    """

    __tablename__ = "quiz_attempts"

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    answers: Mapped[list[int | None] | None] = mapped_column(JSONB)
    score: Mapped[int | None] = mapped_column(Integer)

    # Written by the server, never sent by the client: this column and the one
    # below it are the whole of "giờ tính ở backend".
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The quiz's clock as it stood when this attempt began. Copied for the
    # same reason a submission copies its language: editing the quiz must not
    # rewrite the rules somebody is already playing under.
    time_limit_s: Mapped[int | None] = mapped_column(Integer)

    # Whether the clock ended this attempt rather than the student.
    #
    # A stored column, although it looks derivable from `submitted_at` against
    # the deadline. It is not, quite: an answer arriving a second or two late
    # is accepted and marked normally, so "submitted after the deadline" and
    # "cut off by the deadline" are different facts, and an attempt abandoned
    # without submitting is finalised *at* its deadline, where both readings
    # of a comparison are defensible. One boolean written by the code that
    # made the decision beats three readers re-deriving it differently.
    expired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        # An attempt is either running or finished, and the three columns that
        # describe a finished one move together. A row that carries a score
        # but no submission time is not a state this feature has -- it is a
        # half-applied write.
        CheckConstraint(
            "(submitted_at IS NULL AND score IS NULL AND answers IS NULL) "
            "OR (submitted_at IS NOT NULL AND score IS NOT NULL AND answers IS NOT NULL)",
            name="ck_quiz_attempts_finished",
        ),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_quiz_attempts_score"),
        # Running out of time is worth no marks, and there is nothing else it
        # could be worth: nothing is saved while the attempt runs, so an
        # attempt the clock ended has no answers to mark. Written down here so
        # that a future endpoint cannot quietly invent a partial score.
        CheckConstraint(
            "expired = false OR (submitted_at IS NOT NULL AND score = 0)",
            name="ck_quiz_attempts_expired_scores_zero",
        ),
        CheckConstraint(
            f"time_limit_s IS NULL OR time_limit_s BETWEEN "
            f"{MIN_TIME_LIMIT_S} AND {MAX_TIME_LIMIT_S}",
            name="ck_quiz_attempts_time_limit",
        ),
        # One clock per person per quiz. Partial, so finished attempts pile up
        # freely -- history is the point of keeping them.
        Index(
            "uq_quiz_attempts_open",
            "quiz_id",
            "user_id",
            unique=True,
            postgresql_where=text("submitted_at IS NULL"),
        ),
        # The history panel: this person's attempts at this quiz, newest first.
        Index("ix_quiz_attempts_quiz_user", "quiz_id", "user_id", text("started_at DESC")),
    )

    def __repr__(self) -> str:
        state = "in progress" if self.submitted_at is None else f"{self.score}%"
        return f"<QuizAttempt {state}>"
