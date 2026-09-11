"""Code exercise endpoints: authoring, reading, and submitting.

Paths follow the curriculum's shape -- a collection hangs off its parent, a
row stands on its own -- and the split that matters is by audience rather than
by verb. `GET /code-exercises/{id}/test-cases` answers two different questions
depending on who asks, and it answers them with two different response models:
`TestCaseOut` for the instructor who wrote the answer key, `TestCaseSample`
for everyone else, which has no field an answer key could travel in.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import SubmissionResult, TestCase
from app.schemas.grading import (
    CodeExerciseCreate,
    CodeExerciseOut,
    CodeExerciseUpdate,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionOut,
    SubmissionResultOut,
    TestCaseCreate,
    TestCaseOrder,
    TestCaseOut,
    TestCaseSample,
    TestCaseUpdate,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import grading as grading_service
from app.services.rate_limit import RateLimiter, get_rate_limiter

router = APIRouter(tags=["grading"])

#: Redis-backed, and overridden in tests. Only the submit route takes it: it is
#: the one endpoint here that puts work on a queue.
RateLimit = Annotated[RateLimiter, Depends(get_rate_limiter)]


def sample_out(case: TestCase) -> TestCaseSample:
    """A test case as a student may see it.

    The input and the expected output are copied across **only** when the case
    is not hidden. For a hidden one the fields stay null, and the model has no
    other place they could appear -- which is the point of it being a separate
    model rather than the same one with fields blanked out.
    """
    return TestCaseSample(
        id=case.id,
        position=case.position,
        is_hidden=case.is_hidden,
        score_weight=case.score_weight,
        sample_input=None if case.is_hidden else case.input,
        sample_output=None if case.is_hidden else case.expected_output,
    )


def result_out(result: SubmissionResult, case: TestCase) -> SubmissionResultOut:
    return SubmissionResultOut(
        test_case_id=case.id,
        position=case.position,
        is_hidden=case.is_hidden,
        verdict=result.verdict,
        run_time_ms=result.run_time_ms,
        # Belt and braces: the worker never writes this for a hidden case, and
        # the API would not return it even if a row somehow had one.
        stdout_trunc=None if case.is_hidden else result.stdout_trunc,
    )


# --- Exercises -------------------------------------------------------------


@router.post(
    "/lessons/{lesson_id}/code-exercise",
    response_model=CodeExerciseOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_code_exercise(
    lesson_id: uuid.UUID,
    payload: CodeExerciseCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> CodeExerciseOut:
    """Attach an exercise to one of your own `code_exercise` lessons."""
    exercise = await grading_service.create_exercise(
        session, lesson_id, current_user, payload
    )
    return CodeExerciseOut.model_validate(exercise)


@router.get("/lessons/{lesson_id}/code-exercise", response_model=CodeExerciseOut)
async def get_code_exercise_of_lesson(
    lesson_id: uuid.UUID, viewer: OptionalUser, session: DbSession
) -> CodeExerciseOut:
    """The exercise behind a lesson, for anyone who may open that lesson.

    The statement and the limits, and nothing about the test cases: those come
    from their own endpoint, which decides per caller what may be shown.
    """
    exercise = await grading_service.get_exercise_of_lesson(session, lesson_id, viewer)
    return CodeExerciseOut.model_validate(exercise)


@router.patch("/code-exercises/{exercise_id}", response_model=CodeExerciseOut)
async def update_code_exercise(
    exercise_id: uuid.UUID,
    payload: CodeExerciseUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> CodeExerciseOut:
    exercise = await grading_service.update_exercise(
        session, exercise_id, current_user, payload
    )
    return CodeExerciseOut.model_validate(exercise)


@router.delete("/code-exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_code_exercise(
    exercise_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Delete the exercise, its test cases and every submission made to it."""
    await grading_service.delete_exercise(session, exercise_id, current_user)


# --- Test cases ------------------------------------------------------------


@router.get(
    "/code-exercises/{exercise_id}/test-cases",
    response_model=list[TestCaseOut] | list[TestCaseSample],
)
async def list_test_cases(
    exercise_id: uuid.UUID, viewer: OptionalUser, session: DbSession
) -> list[TestCaseOut] | list[TestCaseSample]:
    """The test cases, in the detail the caller is entitled to.

    The instructor who owns the exercise gets the answer key. Everyone else
    gets the list with the sample cases filled in and the hidden ones present
    but empty -- enough to know the exercise has eight cases and what each is
    worth, which is how it is marked, and nothing about how to pass it.
    """
    exercise = await grading_service.exercise_for_viewer(session, exercise_id, viewer)

    if await grading_service.may_manage_exercise(session, exercise, viewer):
        cases = await grading_service.list_test_cases(session, exercise_id, viewer)
        return [TestCaseOut.model_validate(case) for case in cases]

    cases = await grading_service.list_test_cases_for_viewer(
        session, exercise_id, viewer
    )
    return [sample_out(case) for case in cases]


@router.post(
    "/code-exercises/{exercise_id}/test-cases",
    response_model=TestCaseOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    exercise_id: uuid.UUID,
    payload: TestCaseCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> TestCaseOut:
    """Append a test case. Hidden unless the instructor says otherwise."""
    case = await grading_service.create_test_case(
        session, exercise_id, current_user, payload
    )
    return TestCaseOut.model_validate(case)


@router.patch("/test-cases/{test_case_id}", response_model=TestCaseOut)
async def update_test_case(
    test_case_id: uuid.UUID,
    payload: TestCaseUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> TestCaseOut:
    case = await grading_service.update_test_case(
        session, test_case_id, current_user, payload
    )
    return TestCaseOut.model_validate(case)


@router.delete("/test-cases/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    test_case_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    await grading_service.delete_test_case(session, test_case_id, current_user)


@router.put(
    "/code-exercises/{exercise_id}/test-cases/order", response_model=list[TestCaseOut]
)
async def reorder_test_cases(
    exercise_id: uuid.UUID,
    payload: TestCaseOrder,
    current_user: CurrentUser,
    session: DbSession,
) -> list[TestCaseOut]:
    """Set the order of every case at once, as it looks after a drag."""
    cases = await grading_service.reorder_test_cases(
        session, exercise_id, current_user, payload.test_case_ids
    )
    return [TestCaseOut.model_validate(case) for case in cases]


# --- Submissions -----------------------------------------------------------


@router.post(
    "/code-exercises/{exercise_id}/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_submission(
    exercise_id: uuid.UUID,
    payload: SubmissionCreate,
    current_user: CurrentUser,
    session: DbSession,
    limiter: RateLimit,
) -> SubmissionOut:
    """Submit an answer. Comes back `pending`, with no verdict yet.

    The row is committed here and graded by a worker; `pending` is the true
    state of the system at this moment rather than a placeholder. Submitting
    too fast answers 429 with `Retry-After` -- grading is expensive enough
    that one person in a loop is felt by everyone else in the queue.
    """
    submission = await grading_service.create_submission(
        session, exercise_id, current_user, payload.code, limiter
    )
    return SubmissionOut.model_validate(submission)


@router.get(
    "/code-exercises/{exercise_id}/submissions", response_model=Page[SubmissionOut]
)
async def list_my_submissions(
    exercise_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[SubmissionOut]:
    """Your own submission history for this exercise, newest first."""
    rows, total = await grading_service.list_submissions(
        session, exercise_id, current_user, page=page, page_size=page_size
    )
    return Page[SubmissionOut](
        items=[SubmissionOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
async def get_submission(
    submission_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> SubmissionDetail:
    """One submission with its code and per-case results.

    Yours, or one made to an exercise you own. Anyone else gets a 404: whether
    a particular submission id exists is not a stranger's business.
    """
    submission, results = await grading_service.get_submission(
        session, submission_id, current_user
    )
    return SubmissionDetail(
        **SubmissionOut.model_validate(submission).model_dump(),
        code=submission.code,
        results=[result_out(result, case) for result, case in results],
    )
