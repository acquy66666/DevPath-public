"""Request and response shapes for code exercises, test cases and submissions.

The important thing in this file is what is **missing** from one of the
schemas. `TestCaseOut` carries the input and the expected output; the student
sees `TestCaseSample`, which has no field for either. That is deliberate and
structural: the rule "a hidden test case never leaves the server" is enforced
by there being no field to put it in, not by a service remembering to blank it
out. A future endpoint that returns the wrong model is a compile-time-shaped
mistake rather than a silent leak.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.grading import (
    MAX_MEMORY_LIMIT_MB,
    MAX_TIME_LIMIT_MS,
    MIN_MEMORY_LIMIT_MB,
    MIN_TIME_LIMIT_MS,
)

#: Submission statuses that mean the grading is over, one way or another.
TERMINAL_STATUSES = frozenset({"done", "error"})


# --- Code exercises --------------------------------------------------------


class CodeExerciseCreate(BaseModel):
    statement_md: str = Field(min_length=1)
    language: str = "python"
    starter_code: str | None = None
    time_limit_ms: int = Field(default=2000, ge=MIN_TIME_LIMIT_MS, le=MAX_TIME_LIMIT_MS)
    memory_limit_mb: int = Field(
        default=256, ge=MIN_MEMORY_LIMIT_MB, le=MAX_MEMORY_LIMIT_MB
    )


class CodeExerciseUpdate(BaseModel):
    """Every field optional: a PATCH says what changes, not what stays."""

    statement_md: str | None = Field(default=None, min_length=1)
    starter_code: str | None = None
    time_limit_ms: int | None = Field(
        default=None, ge=MIN_TIME_LIMIT_MS, le=MAX_TIME_LIMIT_MS
    )
    memory_limit_mb: int | None = Field(
        default=None, ge=MIN_MEMORY_LIMIT_MB, le=MAX_MEMORY_LIMIT_MB
    )


class CodeExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lesson_id: uuid.UUID
    statement_md: str
    language: str
    starter_code: str | None
    time_limit_ms: int
    memory_limit_mb: int
    created_at: datetime
    updated_at: datetime


# --- Test cases ------------------------------------------------------------


class TestCaseCreate(BaseModel):
    input: str = ""
    expected_output: str
    is_hidden: bool = True
    score_weight: int = Field(default=1, gt=0)


class TestCaseUpdate(BaseModel):
    input: str | None = None
    expected_output: str | None = None
    is_hidden: bool | None = None
    score_weight: int | None = Field(default=None, gt=0)


class TestCaseOut(BaseModel):
    """The instructor's view: everything, including the answer key."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise_id: uuid.UUID
    input: str
    expected_output: str
    is_hidden: bool
    position: int
    score_weight: int


class TestCaseSample(BaseModel):
    """The student's view of a case they are allowed to see.

    Only sample cases are ever rendered through this model. It has no
    `expected_output` for hidden cases to leak through, because it has no
    `expected_output` at all -- the sample answer travels in `sample_output`,
    which the service fills in only for a case whose `is_hidden` is false.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    is_hidden: bool
    sample_input: str | None = None
    sample_output: str | None = None
    score_weight: int


class TestCaseOrder(BaseModel):
    test_case_ids: list[uuid.UUID]


# --- Submissions -----------------------------------------------------------


class SubmissionCreate(BaseModel):
    # A cap so a submission cannot be used to store a file: 64 KB is many
    # times any exercise answer and far below anything worth abusing.
    code: str = Field(min_length=1, max_length=64_000)


class SubmissionResultOut(BaseModel):
    """One test case's outcome.

    `stdout_trunc` is null for hidden cases and stays null: what a program
    printed on secret input describes the secret input.
    """

    model_config = ConfigDict(from_attributes=True)

    test_case_id: uuid.UUID
    position: int
    is_hidden: bool
    verdict: str
    run_time_ms: int | None
    stdout_trunc: str | None


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise_id: uuid.UUID
    user_id: uuid.UUID
    language: str
    status: str
    verdict: str | None
    score: int | None
    run_time_ms: int | None
    peak_memory_mb: int | None
    message: str | None
    created_at: datetime


class SubmissionDetail(SubmissionOut):
    """One submission with the code that was sent and the per-case results.

    `total_cases` is here so this response answers the same question a live
    progress event does. A client that lost its WebSocket and fell back to
    polling gets "3 of 8 done" from here, rather than being able to count only
    the results that have arrived and never knowing what it is counting
    towards.
    """

    code: str
    total_cases: int = 0
    results: list[SubmissionResultOut] = []


# --- Grading progress events ------------------------------------------------


class GradingCaseEvent(BaseModel):
    """One test case, the moment it finished.

    The same three facts the finished submission already shows: which case,
    whether it is hidden, and the letter. There is deliberately no field for
    what the program printed -- not even for a sample case. Output belongs to
    `GET /submissions/{id}`, which is the one place the hidden-case rule is
    written down and tested, and a second place to send output is a second
    place to get it wrong.
    """

    position: int
    is_hidden: bool
    verdict: str
    run_time_ms: int | None = None


class GradingEvent(BaseModel):
    """What a client watching a submission is told, over any transport.

    Two kinds, distinguished by `type`:

    * `snapshot` -- read from the database. Authoritative, and the first thing
      a socket sends, so a client that connects late is not waiting for an
      event that has already been published.
    * `progress` -- published by the worker as it goes. Redis pub/sub is
      fire-and-forget: nobody listening means nobody hears it, and there is no
      replay. So progress makes the wait legible, and snapshots make it true.

    Nothing here carries code, output, a compiler message or a test case's
    input. It is a progress bar, not a result: the result is fetched from the
    REST endpoint when `status` becomes terminal.
    """

    type: str = "progress"
    submission_id: uuid.UUID
    status: str
    total_cases: int = 0
    completed_cases: int = 0
    case: GradingCaseEvent | None = None
    verdict: str | None = None
    score: int | None = None

    @property
    def is_terminal(self) -> bool:
        """Whether there is anything left to wait for."""
        return self.status in TERMINAL_STATUSES
