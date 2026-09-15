"""Quizzes, their questions, and sitting one under a clock.

Two audiences again, and the split is sharper here than anywhere else in the
codebase: the instructor writes the answers, and the student must not read
them until the attempt is over. Nothing in this module hands a `QuizQuestion`
to a caller and trusts the layer above to blank a field -- the router picks a
response model per audience, and the models differ by which fields exist.

The clock is the other thing this module is about, and the rule is one
sentence: **the deadline is computed here, from `started_at` and the
`time_limit_s` copied onto the attempt when it began.** The browser's
countdown is decoration. Three consequences follow, and all three are visible
in `submit_attempt`:

* an answer that arrives a little late is still counted (`SUBMIT_GRACE_S`),
  because the round trip is not the student's fault;
* an answer that arrives long after is not, and the attempt is marked
  `expired` and scored zero;
* an attempt nobody ever submitted is finalised the same way the next time
  anyone looks at it, which is what releases the one-open-attempt slot.

Nothing is saved while an attempt runs. That is a deliberate trade -- no write
per click -- and the cost is that running out of time means having nothing to
be marked on. It is recorded in `docs/report/assets/decisions.md`.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Quiz, QuizAttempt, QuizQuestion, User
from app.schemas.quiz import (
    QuestionCreate,
    QuestionUpdate,
    QuizCreate,
    QuizUpdate,
    check_question_shape,
)
from app.services import curriculum as curriculum_service
from app.services import progress as progress_service

#: How long after the deadline an answer is still marked normally.
#:
#: The student pressed submit in time and the request spent its seconds on the
#: network. Refusing that is punishing a slow connection, and the window is
#: far too short to be worth cheating with: ten seconds buys no answers.
SUBMIT_GRACE_S = 10


class QuizNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "QUIZ_NOT_FOUND"


class QuizExistsError(DomainError):
    """One lesson, one quiz -- the unique constraint, said in advance."""

    status_code = status.HTTP_409_CONFLICT
    code = "QUIZ_EXISTS"


class LessonNotQuizError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "LESSON_NOT_QUIZ"


class QuestionNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "QUESTION_NOT_FOUND"


class InvalidQuestionError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_QUESTION"


class QuizPublishedError(DomainError):
    """The questions of a published quiz are frozen.

    Not a rule about tidiness: an attempt in progress was started against
    these questions and will be marked against `correct_index` as it stands at
    submit time. Editing the key underneath somebody halfway through a quiz
    marks them against a question they were never shown. Unpublish first --
    which, by the same argument, is why unpublishing is refused while an
    attempt is running.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "QUIZ_PUBLISHED"


class QuizEmptyError(DomainError):
    """Nothing to answer. Publishing this would show a student a blank page."""

    status_code = status.HTTP_409_CONFLICT
    code = "QUIZ_EMPTY"


class QuizNotPublishedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "QUIZ_NOT_PUBLISHED"


class AttemptInProgressError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "ATTEMPT_IN_PROGRESS"


class AttemptNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "ATTEMPT_NOT_FOUND"


class AttemptFinishedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "ATTEMPT_ALREADY_SUBMITTED"


class InvalidAnswersError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_ANSWERS"


# --- The clock -------------------------------------------------------------


def deadline_of(attempt: QuizAttempt) -> datetime | None:
    """When this attempt stops counting, or None if it is untimed."""
    if attempt.time_limit_s is None:
        return None
    return attempt.started_at + timedelta(seconds=attempt.time_limit_s)


def seconds_remaining(attempt: QuizAttempt, now: datetime | None = None) -> int | None:
    """Whole seconds left, never negative. None for an untimed attempt.

    Computed against the server's clock and sent with every response about a
    running attempt, so that a browser with a wrong clock still stops at the
    right moment.
    """
    deadline = deadline_of(attempt)
    if deadline is None:
        return None
    left = (deadline - (now or datetime.now(UTC))).total_seconds()
    return max(int(left), 0)


def is_past_grace(attempt: QuizAttempt, now: datetime) -> bool:
    deadline = deadline_of(attempt)
    return deadline is not None and now > deadline + timedelta(seconds=SUBMIT_GRACE_S)


def score_answers(questions: list[QuizQuestion], answers: list[int | None]) -> int:
    """Percentage of questions answered correctly, rounded to a whole number.

    Every question counts the same. Weighted questions would need a column and
    a rule about what the weights mean, and no part of this phase asks for one.
    """
    correct = sum(
        1
        for question, answer in zip(questions, answers, strict=True)
        if answer == question.correct_index
    )
    return round(correct * 100 / len(questions))


# --- Loading and permissions ----------------------------------------------


async def _load_quiz(session: AsyncSession, quiz_id: uuid.UUID) -> Quiz:
    quiz = await session.get(Quiz, quiz_id)
    if quiz is None:
        raise QuizNotFoundError("Không tìm thấy bài trắc nghiệm")
    return quiz


async def quiz_for_management(session: AsyncSession, quiz_id: uuid.UUID, user: User) -> Quiz:
    """A quiz the caller may edit, or a 403/404 explaining why not."""
    quiz = await _load_quiz(session, quiz_id)
    await curriculum_service.lesson_for_management(session, quiz.lesson_id, user)
    return quiz


async def quiz_for_viewer(session: AsyncSession, quiz_id: uuid.UUID, viewer: User | None) -> Quiz:
    """A quiz the caller may read, judged by the lesson it belongs to."""
    quiz = await _load_quiz(session, quiz_id)
    await curriculum_service.get_lesson_for_viewer(session, quiz.lesson_id, viewer)
    return quiz


async def may_manage_quiz(session: AsyncSession, quiz: Quiz, user: User | None) -> bool:
    """Whether this caller is the one who wrote the quiz.

    Answers with a boolean because it decides *which view* to return rather
    than whether to refuse, and asks the same question `quiz_for_management`
    asks so that "your course" keeps exactly one definition.
    """
    if user is None:
        return False
    try:
        await curriculum_service.lesson_for_management(session, quiz.lesson_id, user)
    except DomainError:
        return False
    return True


async def questions_of(session: AsyncSession, quiz_id: uuid.UUID) -> list[QuizQuestion]:
    rows = await session.scalars(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.position)
    )
    return list(rows)


async def count_questions(session: AsyncSession, quiz_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count()).select_from(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
    )
    return total or 0


async def _has_open_attempt(session: AsyncSession, quiz_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(QuizAttempt.id)
        .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.submitted_at.is_(None))
        .limit(1)
    )
    return found is not None


# --- Quizzes ---------------------------------------------------------------


async def create_quiz(
    session: AsyncSession, lesson_id: uuid.UUID, user: User, payload: QuizCreate
) -> Quiz:
    """Attach a quiz to one of your own `quiz` lessons."""
    lesson, _, _ = await curriculum_service.lesson_for_management(session, lesson_id, user)

    if lesson.type != "quiz":
        raise LessonNotQuizError("Bài học này không phải dạng trắc nghiệm")

    existing = await session.scalar(select(Quiz).where(Quiz.lesson_id == lesson_id))
    if existing is not None:
        raise QuizExistsError("Bài học này đã có bài trắc nghiệm")

    quiz = Quiz(
        lesson_id=lesson_id,
        time_limit_s=payload.time_limit_s,
        pass_score=payload.pass_score,
    )
    session.add(quiz)
    await session.commit()
    # Server-generated columns -- the id and the timestamps -- are not loaded
    # by the insert, and the router reads them while building its response.
    # Without this the first attribute access is lazy IO from sync code.
    await session.refresh(quiz)
    return quiz


async def get_quiz_of_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, viewer: User | None
) -> Quiz:
    """The quiz behind a lesson, if the lesson may be opened at all."""
    await curriculum_service.get_lesson_for_viewer(session, lesson_id, viewer)

    quiz = await session.scalar(select(Quiz).where(Quiz.lesson_id == lesson_id))
    if quiz is None:
        raise QuizNotFoundError("Bài học này chưa có bài trắc nghiệm")
    return quiz


async def update_quiz(
    session: AsyncSession, quiz_id: uuid.UUID, user: User, payload: QuizUpdate
) -> Quiz:
    """Change the clock, the pass mark, or whether students can see it.

    `exclude_unset` rather than a None check: for `time_limit_s`, omitting the
    field and sending null mean two different things, and only the set of keys
    actually sent can tell them apart.
    """
    quiz = await quiz_for_management(session, quiz_id, user)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("is_published") is True and await count_questions(session, quiz.id) == 0:
        raise QuizEmptyError("Bài trắc nghiệm chưa có câu hỏi nào để xuất bản")

    if changes.get("is_published") is False and await _has_open_attempt(session, quiz.id):
        # Same argument as freezing the questions: somebody is sitting this
        # right now, and pulling it out from under them loses their attempt.
        raise AttemptInProgressError(
            "Đang có học viên làm bài này — chờ họ nộp rồi hãy gỡ xuất bản"
        )

    for field, value in changes.items():
        setattr(quiz, field, value)

    await session.commit()
    await session.refresh(quiz)
    return quiz


async def delete_quiz(session: AsyncSession, quiz_id: uuid.UUID, user: User) -> None:
    """Delete the quiz, its questions and every attempt at it."""
    quiz = await quiz_for_management(session, quiz_id, user)
    await session.delete(quiz)
    await session.commit()


# --- Questions -------------------------------------------------------------


async def _question_for_management(
    session: AsyncSession, question_id: uuid.UUID, user: User
) -> tuple[QuizQuestion, Quiz]:
    question = await session.get(QuizQuestion, question_id)
    if question is None:
        raise QuestionNotFoundError("Không tìm thấy câu hỏi")
    quiz = await quiz_for_management(session, question.quiz_id, user)
    return question, quiz


def _refuse_if_published(quiz: Quiz) -> None:
    if quiz.is_published:
        raise QuizPublishedError(
            "Bài trắc nghiệm đang xuất bản — gỡ xuất bản trước khi sửa câu hỏi"
        )


async def add_question(
    session: AsyncSession, quiz_id: uuid.UUID, user: User, payload: QuestionCreate
) -> QuizQuestion:
    """Append a question to a draft quiz."""
    quiz = await quiz_for_management(session, quiz_id, user)
    _refuse_if_published(quiz)

    question = QuizQuestion(
        quiz_id=quiz.id,
        question=payload.question,
        options=payload.options,
        correct_index=payload.correct_index,
        explanation=payload.explanation,
        position=await count_questions(session, quiz.id),
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return question


async def update_question(
    session: AsyncSession, question_id: uuid.UUID, user: User, payload: QuestionUpdate
) -> QuizQuestion:
    """Edit one question of a draft quiz.

    The cross-field rules are checked on the *merged* question rather than on
    what was sent: changing `options` alone can make an untouched
    `correct_index` point past the end, and the row that results is a question
    with no right answer.
    """
    question, quiz = await _question_for_management(session, question_id, user)
    _refuse_if_published(quiz)

    changes = payload.model_dump(exclude_unset=True)
    merged = {
        "question": changes.get("question", question.question),
        "options": changes.get("options", list(question.options)),
        "correct_index": changes.get("correct_index", question.correct_index),
    }
    try:
        check_question_shape(**merged)
    except ValueError as exc:
        raise InvalidQuestionError(str(exc)) from exc

    for field, value in changes.items():
        setattr(question, field, value)

    await session.commit()
    await session.refresh(question)
    return question


async def delete_question(session: AsyncSession, question_id: uuid.UUID, user: User) -> None:
    """Remove a question from a draft quiz and close the gap it leaves."""
    question, quiz = await _question_for_management(session, question_id, user)
    _refuse_if_published(quiz)

    await session.delete(question)
    await session.flush()

    for index, row in enumerate(await questions_of(session, quiz.id)):
        row.position = index
    await session.commit()


# --- Attempts --------------------------------------------------------------


async def _finalise_expired(
    session: AsyncSession, attempt: QuizAttempt, question_count: int
) -> None:
    """Close an attempt the clock ended, scoring it zero.

    Called wherever an expired-but-open attempt is found rather than by a
    scheduled job: the row only matters when somebody looks at it, and a
    student who abandoned a quiz must not be locked out of the next attempt by
    a slot nothing ever released.

    `submitted_at` is the deadline, not the moment this ran. The attempt ended
    when time ran out; that a page happened to be opened three days later is
    not a fact about the attempt.
    """
    attempt.submitted_at = deadline_of(attempt)
    attempt.answers = [None] * question_count
    attempt.score = 0
    attempt.expired = True


async def start_attempt(
    session: AsyncSession, quiz_id: uuid.UUID, user: User
) -> tuple[QuizAttempt, Quiz, list[QuizQuestion]]:
    """Begin an attempt -- or hand back the one already running.

    Resuming rather than refusing is the whole reason this is idempotent: a
    refresh, a dropped connection or a second tab must not cost a student
    their clock, and must not give them a second one either. The partial
    unique index is the backstop if two requests race.
    """
    quiz = await quiz_for_viewer(session, quiz_id, user)

    if not quiz.is_published and not await may_manage_quiz(session, quiz, user):
        raise QuizNotPublishedError("Bài trắc nghiệm này chưa được xuất bản")

    questions = await questions_of(session, quiz.id)
    if not questions:
        raise QuizEmptyError("Bài trắc nghiệm này chưa có câu hỏi nào")

    open_attempt = await session.scalar(
        select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.user_id == user.id,
            QuizAttempt.submitted_at.is_(None),
        )
    )
    if open_attempt is not None:
        if not is_past_grace(open_attempt, datetime.now(UTC)):
            return open_attempt, quiz, questions
        await _finalise_expired(session, open_attempt, len(questions))
        await session.flush()

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user.id,
        # Python's clock rather than the column's server default, so that every
        # comparison this feature makes -- start, deadline, submit -- is made
        # against one clock instead of two that can drift apart.
        started_at=datetime.now(UTC),
        time_limit_s=quiz.time_limit_s,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt, quiz, questions


async def get_attempt(
    session: AsyncSession, attempt_id: uuid.UUID, user: User
) -> tuple[QuizAttempt, Quiz, list[QuizQuestion]]:
    """One attempt of your own, running or finished.

    Somebody else's attempt is reported as not found rather than forbidden:
    "this id exists but is not yours" is a fact about another student that
    nobody asking has a right to.
    """
    attempt = await session.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise AttemptNotFoundError("Không tìm thấy lượt làm bài")

    quiz = await _load_quiz(session, attempt.quiz_id)
    questions = await questions_of(session, quiz.id)

    if attempt.submitted_at is None and is_past_grace(attempt, datetime.now(UTC)):
        await _finalise_expired(session, attempt, len(questions))
        await session.commit()

    return attempt, quiz, questions


async def submit_attempt(
    session: AsyncSession,
    attempt_id: uuid.UUID,
    user: User,
    answers: list[int | None],
) -> tuple[QuizAttempt, Quiz, list[QuizQuestion]]:
    """Mark an attempt and close it.

    The order of the checks is the feature: **the clock is read before the
    answers are**. Whatever arrives after the grace window is marked zero
    without being looked at, which is what makes the time limit a limit rather
    than a suggestion the client is asked to honour.
    """
    attempt = await session.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise AttemptNotFoundError("Không tìm thấy lượt làm bài")
    if attempt.submitted_at is not None:
        raise AttemptFinishedError("Lượt làm bài này đã nộp rồi")

    quiz = await _load_quiz(session, attempt.quiz_id)
    questions = await questions_of(session, quiz.id)
    now = datetime.now(UTC)

    if is_past_grace(attempt, now):
        await _finalise_expired(session, attempt, len(questions))
        await session.commit()
        return attempt, quiz, questions

    if len(answers) != len(questions):
        raise InvalidAnswersError(
            f"Bài có {len(questions)} câu nhưng nhận được {len(answers)} câu trả lời"
        )
    for index, (question, answer) in enumerate(zip(questions, answers, strict=True)):
        if answer is not None and not 0 <= answer < len(question.options):
            raise InvalidAnswersError(
                f"Câu {index + 1}: không có phương án số {answer}"
            )

    attempt.answers = answers
    attempt.score = score_answers(questions, answers)
    attempt.submitted_at = now

    if attempt.score >= quiz.pass_score:
        # Passing finishes the lesson, exactly as an accepted submission
        # finishes a code exercise -- and in the same transaction, so a
        # completion can never be recorded for an attempt that did not save.
        await progress_service.mark_lesson_solved(
            session, lesson_id=quiz.lesson_id, user_id=user.id
        )

    await session.commit()
    return attempt, quiz, questions


async def list_attempts(
    session: AsyncSession,
    quiz_id: uuid.UUID,
    user: User,
    *,
    page: int,
    page_size: int,
) -> tuple[list[QuizAttempt], int]:
    """This student's own attempts at this quiz, newest first."""
    await quiz_for_viewer(session, quiz_id, user)

    where = (QuizAttempt.quiz_id == quiz_id) & (QuizAttempt.user_id == user.id)
    total = await session.scalar(select(func.count()).select_from(QuizAttempt).where(where))
    rows = await session.scalars(
        select(QuizAttempt)
        .where(where)
        .order_by(QuizAttempt.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total or 0
