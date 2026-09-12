"""Code exercises, test cases, and taking a submission in.

Two audiences with opposite rights meet on the same four tables, and every
function here starts by deciding which one is asking:

* the instructor who owns the course writes the exercise, its limits, and the
  answer key. Ownership is checked by walking up to the course, exactly as the
  curriculum service does -- there is no second definition of "your course".
* the student reads the statement and the sample cases, and submits. What they
  may read is what they may read of the *lesson*: preview, enrolled, or the
  owner. There is no separate rule for exercises, because an exercise a
  student cannot open a lesson to reach should not be reachable by knowing its
  id either.

Grading itself is not here. This module takes a submission in and leaves it
`pending`; the queue and the worker that move it along are the next task, and
keeping the boundary sharp is what lets the API be tested without Docker.
"""

import uuid

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.models import CodeExercise, Submission, SubmissionResult, TestCase, User
from app.schemas.grading import (
    CodeExerciseCreate,
    CodeExerciseUpdate,
    TestCaseCreate,
    TestCaseUpdate,
)
from app.services import curriculum as curriculum_service
from app.services.rate_limit import RateLimiter

# The message left on the row when the queue would not take the job. It is
# read by a student, so it says what to do rather than what broke.
QUEUE_DOWN_MESSAGE = (
    "Hệ thống chấm bài đang bận hoặc tạm ngừng. Bài của bạn chưa được đưa vào "
    "hàng đợi — vui lòng nộp lại sau ít phút."
)


# Keys are prefixed so they are greppable in a Redis that also holds the Celery
# queue, and carry the user id so one person's limit is theirs alone.
COOLDOWN_KEY = "rl:{kind}:cooldown:{user}:{exercise}"
HOURLY_KEY = "rl:submit:hour:{user}"
HOUR_SECONDS = 3600


async def enforce_submission_limits(
    limiter: RateLimiter,
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    *,
    kind: str = "submit",
) -> None:
    """Two gates, cheapest first, both before anything is written or queued.

    The cooldown is per exercise: iterating on one problem is what the wait is
    for, and a student switching to another exercise is not the abuse this
    guards against. The hourly quota is per person across every exercise,
    which is the only one of the two a patient script cannot walk around.

    A trial run gets its **own cooldown** and **shares the hourly quota**. The
    split is deliberate: the normal way to use this page is to try the samples
    and then submit, and one cooldown for both would make the platform refuse
    the very sequence it is teaching. The quota is the gate that actually
    protects the queue, and a trial costs the queue exactly what a submission
    costs it, so that one is shared.
    """
    settings = get_settings()

    wait = await limiter.claim(
        COOLDOWN_KEY.format(kind=kind, user=user_id, exercise=exercise_id),
        settings.submission_cooldown_seconds,
    )
    if wait:
        # Named after the button that was pressed. Telling someone who clicked
        # "chạy thử" that they just submitted is a small lie that makes them
        # check their submission history for something that is not there.
        did, again = (
            ("chạy thử bài tập này", "chạy lại")
            if kind == "trial"
            else ("nộp bài cho bài tập này", "nộp lại")
        )
        raise SubmissionRateLimitedError(
            f"Bạn vừa {did}. Đợi {wait} giây rồi {again} nhé.",
            retry_after=wait,
        )

    wait = await limiter.count(
        HOURLY_KEY.format(user=user_id),
        settings.submission_hourly_limit,
        HOUR_SECONDS,
    )
    if wait:
        minutes = wait // 60 + 1
        raise SubmissionRateLimitedError(
            f"Bạn đã nộp {settings.submission_hourly_limit} bài trong một giờ — "
            f"quá nhiều so với bình thường. Thử lại sau khoảng {minutes} phút.",
            retry_after=wait,
        )


def enqueue_grading(submission_id: uuid.UUID) -> None:
    """Ask a worker to grade this submission.

    A function of its own so a test can replace it: importing Celery does not
    need a broker, but calling `.delay()` does, and no API test should need
    Redis running to check that a submission was accepted.
    """
    from app.workers.grading import grade_submission

    grade_submission.delay(str(submission_id))


class ExerciseNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "EXERCISE_NOT_FOUND"


class ExerciseExistsError(DomainError):
    """One lesson, one exercise -- the unique constraint, said in advance."""

    status_code = status.HTTP_409_CONFLICT
    code = "EXERCISE_EXISTS"


class LessonNotCodeExerciseError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "LESSON_NOT_CODE_EXERCISE"


class TestCaseNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "TEST_CASE_NOT_FOUND"


class InvalidOrderError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_ORDER"


class SubmissionNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "SUBMISSION_NOT_FOUND"


class SubmissionRateLimitedError(DomainError):
    """Too many submissions, too fast.

    Carries `retry_after` so the answer says when to come back; a 429 without
    it can only be answered by guessing, which is another request.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "SUBMISSION_RATE_LIMITED"

    def __init__(self, message: str, *, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


class GradingUnavailableError(DomainError):
    """The submission was taken but nothing can be told to grade it.

    Redis is down, or the queue refused the job. Returning 201 here would be
    the dishonest answer: the student would watch a row that no worker will
    ever pick up.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "GRADING_UNAVAILABLE"


class NoSampleTestCaseError(DomainError):
    """Nothing to try the code against.

    Separate from `EXERCISE_NOT_READY` because it means something different to
    the person reading it: the exercise is fine and can be submitted to, it
    just has no visible case to rehearse against. The page turns this into a
    disabled button rather than an error.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "NO_SAMPLE_TEST_CASES"


class ExerciseNotReadyError(DomainError):
    """No test cases, so there is nothing a submission could be judged against.

    Rejecting the submission is the honest answer. Accepting it would queue
    work whose only possible outcome is a system error, and charge the wait to
    a student who did nothing wrong.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "EXERCISE_NOT_READY"


# --- Loading and permissions ----------------------------------------------


async def _cases_of(session: AsyncSession, exercise_id: uuid.UUID) -> list[TestCase]:
    rows = await session.scalars(
        select(TestCase)
        .where(TestCase.exercise_id == exercise_id)
        .order_by(TestCase.position)
    )
    return list(rows)


async def count_test_cases(
    session: AsyncSession, exercise_id: uuid.UUID, *, samples_only: bool = False
) -> int:
    """How many cases a submission to this exercise will be judged against.

    The denominator of "test 3/8", and it comes from the exercise rather than
    from the results so a page can show it before the first case has run. One
    definition, used by the REST detail and by the live channel's snapshot --
    two counts that disagreed would make the progress bar jump when a socket
    dropped.

    `samples_only` is what a trial run counts against, and it has to be asked
    for here rather than worked out by the caller: a trial that showed "1/8"
    while running the two sample cases would be describing a different run
    from the one happening.
    """
    where = TestCase.exercise_id == exercise_id
    if samples_only:
        where = where & TestCase.is_hidden.is_(False)

    total = await session.scalar(
        select(func.count()).select_from(TestCase).where(where)
    )
    return total or 0


async def _load_exercise(session: AsyncSession, exercise_id: uuid.UUID) -> CodeExercise:
    exercise = await session.get(CodeExercise, exercise_id)
    if exercise is None:
        raise ExerciseNotFoundError("Không tìm thấy bài tập code")
    return exercise


async def exercise_for_management(
    session: AsyncSession, exercise_id: uuid.UUID, user: User
) -> CodeExercise:
    """An exercise the caller may edit, or a 403/404 explaining why not."""
    exercise = await _load_exercise(session, exercise_id)
    await curriculum_service.lesson_for_management(session, exercise.lesson_id, user)
    return exercise


async def exercise_for_viewer(
    session: AsyncSession, exercise_id: uuid.UUID, viewer: User | None
) -> CodeExercise:
    """An exercise the caller may read, judged by the lesson it belongs to."""
    exercise = await _load_exercise(session, exercise_id)
    await curriculum_service.get_lesson_for_viewer(session, exercise.lesson_id, viewer)
    return exercise


async def may_manage_exercise(
    session: AsyncSession, exercise: CodeExercise, user: User | None
) -> bool:
    """Whether this caller is the one who wrote the exercise.

    Used to decide *which view* of a thing to return, so it answers with a
    boolean rather than raising: for a student the answer is "no", not an
    error. It asks the same question `exercise_for_management` asks and
    swallows the refusal, so there is still exactly one definition of "your
    course" -- a second one written as a join here is how the two drift apart.
    """
    if user is None:
        return False
    try:
        await curriculum_service.lesson_for_management(session, exercise.lesson_id, user)
    except DomainError:
        return False
    return True


# --- Exercises -------------------------------------------------------------


async def get_exercise_of_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, viewer: User | None
) -> CodeExercise:
    """The exercise behind a lesson, if the lesson may be opened at all."""
    await curriculum_service.get_lesson_for_viewer(session, lesson_id, viewer)

    exercise = await session.scalar(
        select(CodeExercise).where(CodeExercise.lesson_id == lesson_id)
    )
    if exercise is None:
        raise ExerciseNotFoundError("Bài học này chưa có bài tập code")
    return exercise


async def create_exercise(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    payload: CodeExerciseCreate,
) -> CodeExercise:
    lesson, _, _ = await curriculum_service.lesson_for_management(
        session, lesson_id, user
    )
    if lesson.type != "code_exercise":
        raise LessonNotCodeExerciseError(
            "Chỉ bài học kiểu 'code_exercise' mới gắn được bài tập code"
        )

    existing = await session.scalar(
        select(CodeExercise).where(CodeExercise.lesson_id == lesson_id)
    )
    if existing is not None:
        raise ExerciseExistsError("Bài học này đã có bài tập code")

    exercise = CodeExercise(
        lesson_id=lesson.id,
        statement_md=payload.statement_md,
        language=payload.language,
        starter_code=payload.starter_code,
        time_limit_ms=payload.time_limit_ms,
        memory_limit_mb=payload.memory_limit_mb,
    )
    session.add(exercise)
    await session.commit()
    await session.refresh(exercise)
    return exercise


async def update_exercise(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    user: User,
    payload: CodeExerciseUpdate,
) -> CodeExercise:
    exercise = await exercise_for_management(session, exercise_id, user)

    # exclude_unset, not exclude_none: `starter_code: null` is how an
    # instructor clears the starter code, and it must not read as "unchanged".
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(exercise, field, value)

    await session.commit()
    await session.refresh(exercise)
    return exercise


async def delete_exercise(
    session: AsyncSession, exercise_id: uuid.UUID, user: User
) -> None:
    """Delete the exercise, its test cases, and every submission to it.

    A hard delete, and it takes real student work with it through the
    cascades. That is the instructor's call to make about their own lesson --
    the alternative, orphan submissions to an exercise that no longer states
    what they were answering, is worse than nothing.
    """
    exercise = await exercise_for_management(session, exercise_id, user)
    await session.delete(exercise)
    await session.commit()


# --- Test cases ------------------------------------------------------------


async def list_test_cases(
    session: AsyncSession, exercise_id: uuid.UUID, user: User
) -> list[TestCase]:
    """Every case with its answer key. Owner only."""
    await exercise_for_management(session, exercise_id, user)
    return await _cases_of(session, exercise_id)


async def list_test_cases_for_viewer(
    session: AsyncSession, exercise_id: uuid.UUID, viewer: User | None
) -> list[TestCase]:
    """Every case a student is allowed to know *about*.

    Hidden cases are included, and that is on purpose: knowing there are eight
    of them, and what they are worth, tells a student how the exercise is
    marked without telling them any answer. The router renders these through
    `TestCaseSample`, which has nowhere to put an input or an expected output.
    """
    await exercise_for_viewer(session, exercise_id, viewer)
    return await _cases_of(session, exercise_id)


async def create_test_case(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    user: User,
    payload: TestCaseCreate,
) -> TestCase:
    await exercise_for_management(session, exercise_id, user)
    existing = await _cases_of(session, exercise_id)

    case = TestCase(
        exercise_id=exercise_id,
        input=payload.input,
        expected_output=payload.expected_output,
        is_hidden=payload.is_hidden,
        score_weight=payload.score_weight,
        position=len(existing),
    )
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case


async def _case_for_management(
    session: AsyncSession, test_case_id: uuid.UUID, user: User
) -> TestCase:
    case = await session.get(TestCase, test_case_id)
    if case is None:
        raise TestCaseNotFoundError("Không tìm thấy test case")
    await exercise_for_management(session, case.exercise_id, user)
    return case


async def update_test_case(
    session: AsyncSession,
    test_case_id: uuid.UUID,
    user: User,
    payload: TestCaseUpdate,
) -> TestCase:
    case = await _case_for_management(session, test_case_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, field, value)

    await session.commit()
    await session.refresh(case)
    return case


async def delete_test_case(
    session: AsyncSession, test_case_id: uuid.UUID, user: User
) -> None:
    case = await _case_for_management(session, test_case_id, user)
    exercise_id = case.exercise_id

    await session.delete(case)
    await session.flush()

    for index, remaining in enumerate(await _cases_of(session, exercise_id)):
        remaining.position = index
    await session.commit()


async def reorder_test_cases(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    user: User,
    test_case_ids: list[uuid.UUID],
) -> list[TestCase]:
    """Set the order of every case at once, as it looks after a drag.

    Whole-list, like the curriculum: the client sends the arrangement it wants
    rather than a move instruction, and a list that is not exactly the current
    set is rejected rather than half-applied.
    """
    await exercise_for_management(session, exercise_id, user)
    cases = await _cases_of(session, exercise_id)

    by_id = {case.id: case for case in cases}
    if len(test_case_ids) != len(by_id) or set(test_case_ids) != set(by_id):
        raise InvalidOrderError("Danh sách test case phải chứa đúng các case hiện có")

    for index, case_id in enumerate(test_case_ids):
        by_id[case_id].position = index
    await session.commit()

    return await _cases_of(session, exercise_id)


# --- Submissions -----------------------------------------------------------


async def create_submission(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    user: User,
    code: str,
    limiter: RateLimiter,
    *,
    is_trial: bool = False,
) -> Submission:
    """Take a submission in and hand it to the grading queue.

    The row is committed as `pending` **before** the job is queued, and that
    order is the whole of it: a worker is fast and would otherwise be handed
    an id that is not in the database yet. The cost of this order is a row
    that exists while the queue is down, which is why the failure below is
    written into the row rather than swallowed.

    A trial run takes the same path with `is_trial=True`. What changes is what
    it is judged against -- the worker runs only the sample cases -- and that
    it stays out of the history. Nothing about the sandbox, the queue or the
    retries differs, because none of those should.
    """
    exercise = await exercise_for_viewer(session, exercise_id, user)

    cases = await _cases_of(session, exercise_id)
    if is_trial:
        # A trial with no sample case has nothing to run against. Refusing is
        # the honest answer: the alternative is a run that grades zero cases
        # and comes back SE, blaming the platform for an empty exercise.
        if not any(not case.is_hidden for case in cases):
            raise NoSampleTestCaseError(
                "Bài tập này không có test case mẫu nào để chạy thử"
            )
    elif not cases:
        raise ExerciseNotReadyError("Bài tập chưa có test case nào để chấm")

    # Last of the refusals and first of the work: everything above is about
    # whether this submission is possible at all, and a caller who cannot see
    # the exercise should not learn about our rate limits instead of a 404.
    await enforce_submission_limits(
        limiter, user.id, exercise.id, kind="trial" if is_trial else "submit"
    )

    submission = Submission(
        user_id=user.id,
        exercise_id=exercise.id,
        code=code,
        # From the exercise, not from the client: what language a submission is
        # graded as is not the submitter's decision.
        language=exercise.language,
        status="pending",
        is_trial=is_trial,
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)

    try:
        enqueue_grading(submission.id)
    except Exception as exc:
        # Park it immediately rather than leaving a pending row nothing will
        # ever pick up. The student is told now, while they are still looking
        # at the page.
        submission.status = "error"
        submission.message = QUEUE_DOWN_MESSAGE
        await session.commit()
        raise GradingUnavailableError(
            "Hàng đợi chấm bài không nhận được bài nộp"
        ) from exc

    return submission


async def list_submissions(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    user: User,
    *,
    page: int,
    page_size: int,
) -> tuple[list[Submission], int]:
    """Your own attempts at one exercise, newest first.

    Only your own, even for the instructor who owns the exercise: reading
    another student's submissions is a different feature with a different
    audience, and it is not this one.

    Trial runs are left out. History is the record of what a student handed
    in; mixing in every press of "chạy thử" would bury it, and a page of forty
    rehearsals is not a record of anything.
    """
    await exercise_for_viewer(session, exercise_id, user)

    mine = (
        (Submission.exercise_id == exercise_id)
        & (Submission.user_id == user.id)
        & Submission.is_trial.is_(False)
    )
    total = await session.scalar(select(func.count()).select_from(Submission).where(mine))

    rows = await session.scalars(
        select(Submission)
        .where(mine)
        # id as the tiebreaker: two submissions in the same millisecond would
        # otherwise have no fixed order, which is how a row appears on two
        # pages or on none.
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total or 0


async def get_submission(
    session: AsyncSession, submission_id: uuid.UUID, user: User
) -> tuple[Submission, list[tuple[SubmissionResult, TestCase]]]:
    """One submission and its per-case results.

    Readable by the student who sent it and by the instructor who owns the
    exercise -- the second is what makes "why was I marked wrong?" answerable.
    Anyone else gets a 404 rather than a 403: that a given submission id
    exists is not something a stranger should learn.
    """
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise SubmissionNotFoundError("Không tìm thấy bài nộp")

    if submission.user_id != user.id:
        exercise = await _load_exercise(session, submission.exercise_id)
        if not await may_manage_exercise(session, exercise, user):
            raise SubmissionNotFoundError("Không tìm thấy bài nộp")

    rows = await session.execute(
        select(SubmissionResult, TestCase)
        .join(TestCase, TestCase.id == SubmissionResult.test_case_id)
        .where(SubmissionResult.submission_id == submission.id)
        .order_by(TestCase.position)
    )
    return submission, [(result, case) for result, case in rows]
