"""Code exercises, their test cases, and what happened when someone submitted.

Four tables and one rule that shapes all of them: **the expected output of a
hidden test case must never leave the server.** It is stored here, read by the
grading worker, and compared here; no schema in `app/schemas/grading.py`
serialises it for a student, and the service layer is what decides which cases
a given caller is allowed to see at all.

The second rule is written into the database rather than trusted to the
worker: a submission may not carry a verdict until it is `done`. A row that
says "still running, wrong answer" is a bug that would otherwise be discovered
by a student reading it.
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# One language in v1, and the image per language is what makes adding the next
# one a deployment question rather than a redesign.
CODE_LANGUAGES = ("python",)

SUBMISSION_STATUSES = ("pending", "running", "done", "error")
VERDICTS = ("AC", "WA", "TLE", "MLE", "RE", "CE", "SE")

# The ceilings an instructor may set within. They exist because the numbers on
# this form are multiplied by every student who submits: a generous limit is a
# teaching decision, but a limit that takes the VPS down is not one.
MIN_TIME_LIMIT_MS = 100
MAX_TIME_LIMIT_MS = 10_000
MIN_MEMORY_LIMIT_MB = 16
MAX_MEMORY_LIMIT_MB = 512


class CodeExercise(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The exercise attached to one `code_exercise` lesson.

    One per lesson, enforced by a unique constraint rather than by the code
    that creates it: the lesson is what a student opens, and two exercises
    behind it would make "the exercise" ambiguous everywhere downstream.
    """

    __tablename__ = "code_exercises"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    statement_md: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'python'")
    )
    # What the editor is pre-filled with: a signature to implement, or the
    # input parsing an exercise is not about.
    starter_code: Mapped[str | None] = mapped_column(Text)

    time_limit_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("2000")
    )
    memory_limit_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("256")
    )

    __table_args__ = (
        UniqueConstraint("lesson_id", name="uq_code_exercises_lesson"),
        CheckConstraint("language IN ('python')", name="ck_code_exercises_language"),
        CheckConstraint(
            f"time_limit_ms BETWEEN {MIN_TIME_LIMIT_MS} AND {MAX_TIME_LIMIT_MS}",
            name="ck_code_exercises_time_limit",
        ),
        CheckConstraint(
            f"memory_limit_mb BETWEEN {MIN_MEMORY_LIMIT_MB} AND {MAX_MEMORY_LIMIT_MB}",
            name="ck_code_exercises_memory_limit",
        ),
    )

    def __repr__(self) -> str:
        return f"<CodeExercise lesson={self.lesson_id} {self.language}>"


class TestCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One input and the answer it must produce.

    `is_hidden` is the whole point of the table being separate from the
    statement. A sample case is part of the question -- the student reads it,
    runs against it, and debugs with it. A hidden case is the actual
    examination, and its `expected_output` is the answer key: it is read by the
    worker and by nothing that renders.
    """

    __tablename__ = "test_cases"

    # Not a pytest class, despite the name the domain gave it: importing this
    # into a test module would otherwise be collected and warned about.
    __test__ = False

    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_exercises.id", ondelete="CASCADE"),
        nullable=False,
    )
    input: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)

    # Hidden by default: an instructor who forgets to think about it gives
    # nothing away, and the mistake that costs an exercise its integrity has to
    # be made deliberately.
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Partial marks: how much of the exercise this case is worth relative to
    # the others. Equal weights are the default and the common case.
    score_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )

    __table_args__ = (
        # Deferrable for the same reason the curriculum's is: reordering
        # rewrites several rows in one transaction and passes through states
        # where two of them briefly claim the same slot.
        UniqueConstraint(
            "exercise_id",
            "position",
            name="uq_test_cases_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("score_weight > 0", name="ck_test_cases_score_weight"),
    )

    def __repr__(self) -> str:
        kind = "hidden" if self.is_hidden else "sample"
        return f"<TestCase {self.position} {kind}>"


class Submission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One attempt, and the verdict it eventually got.

    Rows arrive `pending` and are moved along by the grading worker. The
    student's code is kept whether it passed or not: submission history is
    what the exercise page shows, and what an instructor looks at when someone
    asks why their answer was rejected.
    """

    __tablename__ = "submissions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_exercises.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    # Copied from the exercise at submission time rather than joined: an
    # instructor who adds a second language later must not retroactively
    # change what an old submission was graded as.
    language: Mapped[str] = mapped_column(String(20), nullable=False)

    # A trial run: the student pressed "chạy thử" instead of "nộp bài".
    #
    # It is the same row, the same queue and the same sandbox, because it costs
    # exactly the same to run -- what differs is that it is graded against the
    # sample cases only, and that it is left out of the submission history. A
    # separate table would have duplicated the queue, the worker, the progress
    # channel and every rule about who may read a run; a boolean here does not.
    #
    # It is also why a trial can never leak anything: the hidden cases are not
    # part of the run at all, rather than part of it with their output stripped
    # afterwards.
    is_trial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    verdict: Mapped[str | None] = mapped_column(String(3))
    # Percentage of the exercise's total weight that passed, 0-100.
    score: Mapped[int | None] = mapped_column(Integer)
    run_time_ms: Mapped[int | None] = mapped_column(Integer)
    # No memory column, on purpose: Docker cannot say how much a container used
    # once it has exited, and only code inside the sandbox could -- see
    # migration 503c1217538c for why that was not worth it.

    # The compiler's words for CE, ours for SE. Not in the original design and
    # added deliberately: a compile error has no per-case results, so without
    # somewhere to put the message a student is told "CE" and nothing else --
    # a verdict they cannot act on.
    message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'done', 'error')",
            name="ck_submissions_status",
        ),
        CheckConstraint(
            "verdict IS NULL OR verdict IN ('AC', 'WA', 'TLE', 'MLE', 'RE', 'CE', 'SE')",
            name="ck_submissions_verdict",
        ),
        # The invariant the worker cannot be trusted to keep on its own: a
        # verdict is a finished grading, and a row cannot claim one before it
        # is done.
        CheckConstraint(
            "status = 'done' OR verdict IS NULL",
            name="ck_submissions_verdict_requires_done",
        ),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_submissions_score"),
        # The submission history of one student on one exercise, newest first.
        # Partial: history never shows trial runs, and a student who leans on
        # "chạy thử" makes far more of those than of real submissions.
        Index(
            "ix_submissions_user_exercise",
            "user_id",
            "exercise_id",
            text("created_at DESC"),
            postgresql_where=text("is_trial = false"),
        ),
        # Watching the queue: how many are waiting, how many are being graded.
        # Partial, because the rows that matter are a vanishing fraction of the
        # table and the finished ones would otherwise dominate the index.
        Index(
            "ix_submissions_status",
            "status",
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Submission {self.status} {self.verdict or '-'}>"


class SubmissionResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """What one test case did to one submission.

    `stdout_trunc` is filled in only for sample cases. For a hidden one it
    stays NULL -- printing back what the program produced on secret input is
    the same leak as showing the input, one round trip later.
    """

    __tablename__ = "submission_results"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict: Mapped[str] = mapped_column(String(3), nullable=False)
    run_time_ms: Mapped[int | None] = mapped_column(Integer)
    stdout_trunc: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("submission_id", "test_case_id", name="uq_submission_results"),
        CheckConstraint(
            "verdict IN ('AC', 'WA', 'TLE', 'MLE', 'RE', 'CE', 'SE')",
            name="ck_submission_results_verdict",
        ),
    )

    def __repr__(self) -> str:
        return f"<SubmissionResult {self.verdict}>"
