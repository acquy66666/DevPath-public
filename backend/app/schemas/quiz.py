"""Request and response shapes for quizzes, questions and attempts.

The thing to read here is which model has `correct_index` on it and which does
not. `QuestionOut` carries the answer key and goes to the instructor who wrote
it; `QuestionForAttempt` is what a student sitting the quiz receives, and it
has no field an answer or an explanation could travel in. The rule "you may
not read the answer while the clock is running" is therefore structural rather
than remembered -- the same arrangement `schemas/grading.py` uses to keep a
hidden test case's expected output off the wire.

`QuestionReview` is the third shape: the same question *after* submitting,
where the answer key is the point. It exists separately so that showing the
explanation is an explicit choice of model, made once, in the one place where
the attempt is known to be over.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.quiz import (
    DEFAULT_PASS_SCORE,
    MAX_OPTIONS,
    MAX_TIME_LIMIT_S,
    MIN_OPTIONS,
    MIN_TIME_LIMIT_S,
)


def check_question_shape(question: str, options: list[str], correct_index: int) -> None:
    """The rules a question must satisfy that no single field can express.

    Defined once and called from two places -- the create model's validator,
    where every field is present, and the service's update path, where the new
    values have to be merged onto the old row before the question makes sense
    as a whole. A second copy of these rules is how a PATCH ends up accepting
    what a POST rejects.

    Raises ValueError, which Pydantic turns into a 422 on create and the
    service turns into an `INVALID_QUESTION` 400 on update.
    """
    if not question.strip():
        raise ValueError("Nội dung câu hỏi không được để trống")

    cleaned = [option.strip() for option in options]
    if any(not option for option in cleaned):
        raise ValueError("Các phương án không được để trống")

    if len(set(cleaned)) != len(cleaned):
        # Two identical choices make a question with two right answers, or
        # none, depending on which one the student happens to click.
        raise ValueError("Các phương án phải khác nhau")

    if not 0 <= correct_index < len(options):
        raise ValueError(
            f"correct_index phải nằm trong khoảng 0..{len(options) - 1} "
            f"(đang là {correct_index})"
        )


# --- Quizzes ---------------------------------------------------------------


class QuizCreate(BaseModel):
    time_limit_s: int | None = Field(
        default=None, ge=MIN_TIME_LIMIT_S, le=MAX_TIME_LIMIT_S
    )
    pass_score: int = Field(default=DEFAULT_PASS_SCORE, ge=0, le=100)


class QuizUpdate(BaseModel):
    """Every field optional -- and `time_limit_s` genuinely means two things.

    Omitted, it leaves the clock alone; sent as `null`, it removes the clock.
    The service tells them apart with `model_dump(exclude_unset=True)` rather
    than by comparing to None, which cannot distinguish them at all.
    """

    time_limit_s: int | None = Field(
        default=None, ge=MIN_TIME_LIMIT_S, le=MAX_TIME_LIMIT_S
    )
    pass_score: int | None = Field(default=None, ge=0, le=100)
    is_published: bool | None = None


class QuizOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    time_limit_s: int | None
    pass_score: int
    ai_generated: bool
    is_published: bool
    #: How many questions are in it. Not a column -- the router passes it in,
    #: because a page has to decide whether to render "bắt đầu làm bài" before
    #: it is allowed to fetch a single question.
    question_count: int
    created_at: datetime
    updated_at: datetime


# --- Questions -------------------------------------------------------------


class QuestionCreate(BaseModel):
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    correct_index: int = Field(ge=0)
    explanation: str | None = None

    @model_validator(mode="after")
    def shape_is_answerable(self) -> "QuestionCreate":
        check_question_shape(self.question, self.options, self.correct_index)
        return self


class QuestionUpdate(BaseModel):
    """Partial. The cross-field rules are re-checked in the service, on the
    merged row -- here there is not always enough of a question to judge."""

    question: str | None = Field(default=None, min_length=1)
    options: list[str] | None = Field(
        default=None, min_length=MIN_OPTIONS, max_length=MAX_OPTIONS
    )
    correct_index: int | None = Field(default=None, ge=0)
    explanation: str | None = None


class QuestionOut(BaseModel):
    """A question as the instructor who owns it sees it: answer key included."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quiz_id: uuid.UUID
    question: str
    options: list[str]
    correct_index: int
    explanation: str | None
    position: int


class QuestionForAttempt(BaseModel):
    """A question as a student sitting the quiz sees it.

    No `correct_index`, no `explanation`, and no way to add one by accident:
    the fields do not exist on this model.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    question: str
    options: list[str]


class QuestionReview(BaseModel):
    """A question after the attempt is over, with what happened to it."""

    id: uuid.UUID
    position: int
    question: str
    options: list[str]
    your_answer: int | None
    correct_index: int
    explanation: str | None
    is_correct: bool


# --- Attempts --------------------------------------------------------------


class AttemptSubmit(BaseModel):
    """One chosen option per question, in question order; null for skipped.

    A list rather than a map of question id to answer: the questions are
    ordered and fixed for the duration of an attempt, so position is a
    complete address, and a list makes "you left one out" a length check.
    """

    answers: list[int | None]


class AttemptOut(BaseModel):
    """One row of the history panel."""

    id: uuid.UUID
    quiz_id: uuid.UUID
    started_at: datetime
    submitted_at: datetime | None
    score: int | None
    passed: bool | None


class AttemptDetail(BaseModel):
    """An attempt, and everything the page showing it is allowed to know.

    Both states of an attempt are described by this one model, and which
    fields are filled says which state it is in:

    * running -- `questions` is filled, `review` is null, `seconds_remaining`
      counts down.
    * finished -- `review` is filled and carries the answer key; `questions`
      still holds the same questions so a page can render either view without
      a second request.

    `deadline_at` and `seconds_remaining` are both sent on purpose. The
    absolute time is what a page prints; the remaining seconds are computed
    here, against the server's clock, so a browser whose clock is wrong shows
    the wrong deadline but still runs out of time at the right moment.
    """

    id: uuid.UUID
    quiz_id: uuid.UUID
    pass_score: int
    time_limit_s: int | None
    started_at: datetime
    deadline_at: datetime | None
    seconds_remaining: int | None
    submitted_at: datetime | None
    score: int | None
    passed: bool | None
    #: Submitted after the deadline, and scored zero because of it.
    expired: bool
    questions: list[QuestionForAttempt]
    review: list[QuestionReview] | None
