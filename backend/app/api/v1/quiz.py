"""Quiz endpoints: authoring, sitting, and reading the result afterwards.

The split that matters here is not by verb but by who is asking, and it is
made by choosing a response model rather than by filtering fields:

* `GET /quizzes/{id}/questions` is the instructor's view and returns
  `QuestionOut`, answer key included. It is management-only -- a student never
  reaches questions through this path at all.
* `POST /quizzes/{id}/attempts` is the student's, and returns
  `QuestionForAttempt`, which has no field a correct answer could sit in.
* The same attempt read back after submitting carries `review`, where the
  answer key is finally the point.

Every clock decision is made in the service. Nothing here reads a time from
the request body, because there is no time in any request body.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import Quiz, QuizAttempt, QuizQuestion
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.quiz import (
    AttemptDetail,
    AttemptOut,
    AttemptSubmit,
    QuestionCreate,
    QuestionForAttempt,
    QuestionOut,
    QuestionReview,
    QuestionUpdate,
    QuizCreate,
    QuizGenerateOut,
    QuizGenerateRequest,
    QuizOut,
    QuizUpdate,
)
from app.services import quiz as quiz_service
from app.services import quiz_generation as quiz_generation_service
from app.services.llm import JsonModel, get_quiz_model_factory
from app.services.rate_limit import RateLimiter, get_rate_limiter
from app.services.storage import ObjectStorage, get_storage_factory

router = APIRouter(tags=["quiz"])

RateLimit = Annotated[RateLimiter, Depends(get_rate_limiter)]
QuizModelFactory = Annotated[Callable[[], JsonModel], Depends(get_quiz_model_factory)]
StorageFactory = Annotated[Callable[[], ObjectStorage], Depends(get_storage_factory)]


def quiz_out(quiz: Quiz, question_count: int) -> QuizOut:
    return QuizOut(
        id=quiz.id,
        lesson_id=quiz.lesson_id,
        time_limit_s=quiz.time_limit_s,
        pass_score=quiz.pass_score,
        ai_generated=quiz.ai_generated,
        is_published=quiz.is_published,
        question_count=question_count,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
    )


def passed(attempt: QuizAttempt, quiz: Quiz) -> bool | None:
    if attempt.score is None:
        return None
    return attempt.score >= quiz.pass_score


def attempt_out(attempt: QuizAttempt, quiz: Quiz) -> AttemptOut:
    return AttemptOut(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        score=attempt.score,
        passed=passed(attempt, quiz),
    )


def review_of(
    attempt: QuizAttempt, questions: list[QuizQuestion]
) -> list[QuestionReview] | None:
    """The answer key, or None while the attempt is still running.

    The single place in this feature where `correct_index` and `explanation`
    are copied into a response, and it is guarded by one condition: the
    attempt has been submitted. A caller who has not finished gets None, and
    there is no other route by which these two fields reach a student.
    """
    if attempt.submitted_at is None:
        return None

    answers = attempt.answers or [None] * len(questions)
    return [
        QuestionReview(
            id=question.id,
            position=question.position,
            question=question.question,
            options=question.options,
            your_answer=answer,
            correct_index=question.correct_index,
            explanation=question.explanation,
            is_correct=answer == question.correct_index,
        )
        for question, answer in zip(questions, answers, strict=True)
    ]


def attempt_detail(
    attempt: QuizAttempt, quiz: Quiz, questions: list[QuizQuestion]
) -> AttemptDetail:
    return AttemptDetail(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        pass_score=quiz.pass_score,
        time_limit_s=attempt.time_limit_s,
        started_at=attempt.started_at,
        deadline_at=quiz_service.deadline_of(attempt),
        seconds_remaining=(
            None if attempt.submitted_at is not None else quiz_service.seconds_remaining(attempt)
        ),
        submitted_at=attempt.submitted_at,
        score=attempt.score,
        passed=passed(attempt, quiz),
        expired=attempt.expired,
        questions=[QuestionForAttempt.model_validate(question) for question in questions],
        review=review_of(attempt, questions),
    )


# --- Quizzes ---------------------------------------------------------------


@router.post(
    "/lessons/{lesson_id}/quiz",
    response_model=QuizOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_quiz(
    lesson_id: uuid.UUID,
    payload: QuizCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> QuizOut:
    """Attach a quiz to one of your own `quiz` lessons."""
    quiz = await quiz_service.create_quiz(session, lesson_id, current_user, payload)
    return quiz_out(quiz, 0)


@router.get("/lessons/{lesson_id}/quiz", response_model=QuizOut)
async def get_quiz_of_lesson(
    lesson_id: uuid.UUID, viewer: OptionalUser, session: DbSession
) -> QuizOut:
    """The quiz behind a lesson, for anyone who may open that lesson.

    The clock, the pass mark and how many questions there are -- enough to
    render the page in front of the quiz. The questions themselves come from
    starting an attempt.
    """
    quiz = await quiz_service.get_quiz_of_lesson(session, lesson_id, viewer)
    return quiz_out(quiz, await quiz_service.count_questions(session, quiz.id))


@router.patch("/quizzes/{quiz_id}", response_model=QuizOut)
async def update_quiz(
    quiz_id: uuid.UUID,
    payload: QuizUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> QuizOut:
    quiz = await quiz_service.update_quiz(session, quiz_id, current_user, payload)
    return quiz_out(quiz, await quiz_service.count_questions(session, quiz.id))


@router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Delete the quiz, its questions and every attempt at it."""
    await quiz_service.delete_quiz(session, quiz_id, current_user)


# --- Questions -------------------------------------------------------------


@router.get("/quizzes/{quiz_id}/questions", response_model=list[QuestionOut])
async def list_questions(
    quiz_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[QuestionOut]:
    """Every question with its answer key -- for the instructor who owns it.

    Management-only by design, and not a filtered view of a shared endpoint:
    a student has no path to a question except through an attempt, where the
    response model has no answer key on it.
    """
    quiz = await quiz_service.quiz_for_management(session, quiz_id, current_user)
    questions = await quiz_service.questions_of(session, quiz.id)
    return [QuestionOut.model_validate(question) for question in questions]


@router.post(
    "/quizzes/{quiz_id}/questions",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_question(
    quiz_id: uuid.UUID,
    payload: QuestionCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> QuestionOut:
    question = await quiz_service.add_question(session, quiz_id, current_user, payload)
    return QuestionOut.model_validate(question)


@router.patch("/quiz-questions/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: uuid.UUID,
    payload: QuestionUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> QuestionOut:
    question = await quiz_service.update_question(
        session, question_id, current_user, payload
    )
    return QuestionOut.model_validate(question)


@router.post("/quiz-questions/{question_id}/approve", response_model=QuestionOut)
async def approve_question(
    question_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> QuestionOut:
    """Sign off an AI-drafted question as it stands.

    Until every draft in a quiz is approved, edited or deleted, the quiz
    cannot be published (409 `QUIZ_NEEDS_REVIEW`).
    """
    question = await quiz_service.approve_question(session, question_id, current_user)
    return QuestionOut.model_validate(question)


@router.post(
    "/quizzes/{quiz_id}/generate",
    response_model=QuizGenerateOut,
    status_code=status.HTTP_201_CREATED,
)
async def generate_questions(
    quiz_id: uuid.UUID,
    payload: QuizGenerateRequest,
    current_user: CurrentUser,
    session: DbSession,
    limiter: RateLimit,
    make_model: QuizModelFactory,
    make_storage: StorageFactory,
) -> QuizGenerateOut:
    """Draft questions from one lesson of the same course with Gemini.

    The drafts are appended to this draft quiz and wait for review; see
    `services/quiz_generation.py`. Takes about ten seconds -- one model call,
    answered in full rather than streamed, because half a question is no use.
    """
    result = await quiz_generation_service.generate_questions(
        session,
        quiz_id,
        current_user,
        source_lesson_id=payload.source_lesson_id,
        count=payload.count,
        limiter=limiter,
        make_model=make_model,
        make_storage=make_storage,
    )
    return QuizGenerateOut(
        questions=[QuestionOut.model_validate(question) for question in result.questions],
        requested=result.requested,
        created=len(result.questions),
        dropped=result.dropped,
        model=result.model,
        truncated=result.truncated,
    )


@router.delete("/quiz-questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    await quiz_service.delete_question(session, question_id, current_user)


# --- Attempts --------------------------------------------------------------


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=AttemptDetail,
    status_code=status.HTTP_201_CREATED,
)
async def start_attempt(
    quiz_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> AttemptDetail:
    """Start the quiz, or pick up the attempt already running.

    Idempotent on purpose: refreshing the page must not start a second clock,
    and must not lose the first one either. 201 either way -- the answer to
    "give me my attempt" is the attempt.
    """
    attempt, quiz, questions = await quiz_service.start_attempt(
        session, quiz_id, current_user
    )
    return attempt_detail(attempt, quiz, questions)


@router.get("/quiz-attempts/{attempt_id}", response_model=AttemptDetail)
async def get_attempt(
    attempt_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> AttemptDetail:
    """One of your own attempts, with the review if it has been submitted."""
    attempt, quiz, questions = await quiz_service.get_attempt(
        session, attempt_id, current_user
    )
    return attempt_detail(attempt, quiz, questions)


@router.post("/quiz-attempts/{attempt_id}/submit", response_model=AttemptDetail)
async def submit_attempt(
    attempt_id: uuid.UUID,
    payload: AttemptSubmit,
    current_user: CurrentUser,
    session: DbSession,
) -> AttemptDetail:
    """Hand in the answers and get the marked paper back.

    Answers arriving after the grace window are not an error: the attempt
    comes back marked `expired` with a score of zero, because a page that says
    what happened is more use than a 409 that leaves the student guessing.
    """
    attempt, quiz, questions = await quiz_service.submit_attempt(
        session, attempt_id, current_user, payload.answers
    )
    return attempt_detail(attempt, quiz, questions)


@router.get("/quizzes/{quiz_id}/attempts", response_model=Page[AttemptOut])
async def list_attempts(
    quiz_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[AttemptOut]:
    """Your own attempt history for this quiz, newest first."""
    attempts, total = await quiz_service.list_attempts(
        session, quiz_id, current_user, page=page, page_size=page_size
    )
    quiz = await quiz_service.quiz_for_viewer(session, quiz_id, current_user)
    return Page[AttemptOut](
        items=[attempt_out(attempt, quiz) for attempt in attempts],
        total=total,
        page=page,
        page_size=page_size,
    )
