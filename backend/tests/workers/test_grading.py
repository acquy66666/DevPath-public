"""Turning a judgement into rows, without Docker and without Celery.

`run_grading()` takes a session and the function that does the judging, so
everything worth arguing about -- what the score means, what is written down,
what is deliberately not written down -- is testable in milliseconds against a
fake judge. The real one starts containers and is tested in `grader/`.

The test this file exists for is `test_a_hidden_case_keeps_its_output_out_of
_the_database`. Everything the API refuses to hand out is worth nothing if the
worker writes it into a column the API is willing to return.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    CodeExercise,
    Course,
    CourseSection,
    Lesson,
    Submission,
    SubmissionResult,
    TestCase,
    User,
)
from app.workers.grading import (
    STORED_OUTPUT_LIMIT,
    CaseOutcome,
    GradingOutcome,
    cpu_seconds_for,
    park_submission,
    run_grading,
)

SAMPLE_INPUT = "1 2\n"
HIDDEN_OUTPUT = "OUTPUT-OF-A-HIDDEN-CASE-DO-NOT-STORE"


async def make_exercise(
    session: AsyncSession,
    *,
    weights: tuple[int, ...] = (1,),
    hidden: tuple[bool, ...] | None = None,
    time_limit_ms: int = 2000,
    memory_limit_mb: int = 128,
) -> CodeExercise:
    """An exercise with one test case per weight, and a course above it."""
    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash="x",
        role="instructor",
    )
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    session.add_all([instructor, category])
    await session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title="Khóa học",
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    lesson = Lesson(
        section_id=section.id, title="Bài tập", type="code_exercise", position=0
    )
    session.add(lesson)
    await session.flush()

    exercise = CodeExercise(
        lesson_id=lesson.id,
        statement_md="Đọc hai số, in ra tổng.",
        language="python",
        time_limit_ms=time_limit_ms,
        memory_limit_mb=memory_limit_mb,
    )
    session.add(exercise)
    await session.flush()

    is_hidden = hidden if hidden is not None else (True,) * len(weights)
    for position, (weight, secret) in enumerate(zip(weights, is_hidden, strict=True)):
        session.add(
            TestCase(
                exercise_id=exercise.id,
                input=SAMPLE_INPUT,
                expected_output="3\n",
                is_hidden=secret,
                position=position,
                score_weight=weight,
            )
        )
    await session.flush()
    return exercise


async def make_submission(
    session: AsyncSession, exercise: CodeExercise, *, code: str = "print(3)"
) -> Submission:
    student = User(
        email=f"hv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Học viên",
        password_hash="x",
        role="student",
    )
    session.add(student)
    await session.flush()

    submission = Submission(
        user_id=student.id,
        exercise_id=exercise.id,
        code=code,
        language="python",
        status="pending",
    )
    session.add(submission)
    await session.flush()
    return submission


def judging(*verdicts: str, stdout: str = "3\n", message: str = "") -> object:
    """A judge that hands back the verdicts it was built with."""

    def judge(code, cases, *, time_limit_ms, memory_limit_mb):
        judge.seen = {
            "code": code,
            "cases": list(cases),
            "time_limit_ms": time_limit_ms,
            "memory_limit_mb": memory_limit_mb,
        }
        overall = next((v for v in verdicts if v != "AC"), "AC")
        return GradingOutcome(
            verdict=overall,
            message=message,
            cases=tuple(
                CaseOutcome(verdict=verdict, run_time_ms=10 + index, stdout=stdout)
                for index, verdict in enumerate(verdicts)
            ),
        )

    judge.seen = {}
    return judge


async def results_of(
    session: AsyncSession, submission: Submission
) -> list[SubmissionResult]:
    rows = await session.scalars(
        select(SubmissionResult).where(SubmissionResult.submission_id == submission.id)
    )
    return list(rows)


# --- What gets written down ------------------------------------------------


async def test_a_graded_submission_ends_done_with_a_verdict_and_a_score(
    db_session: AsyncSession,
) -> None:
    exercise = await make_exercise(db_session, weights=(1, 1))
    submission = await make_submission(db_session, exercise)

    outcome = await run_grading(
        db_session, submission.id, judge=judging("AC", "AC")
    )

    assert outcome.verdict == "AC"
    await db_session.refresh(submission)
    assert submission.status == "done"
    assert submission.verdict == "AC"
    assert submission.score == 100
    assert len(await results_of(db_session, submission)) == 2


async def test_the_score_counts_weight_and_not_test_cases(
    db_session: AsyncSession,
) -> None:
    """An exercise says how much each case is worth; the score has to agree.

    Counting cases instead would make a one-mark warm-up worth as much as the
    case the exercise is actually about.
    """
    exercise = await make_exercise(db_session, weights=(1, 3))
    submission = await make_submission(db_session, exercise)

    await run_grading(db_session, submission.id, judge=judging("AC", "WA"))

    await db_session.refresh(submission)
    assert submission.verdict == "WA"
    assert submission.score == 25


async def test_the_verdict_is_the_first_failure_not_the_last(
    db_session: AsyncSession,
) -> None:
    exercise = await make_exercise(db_session, weights=(1, 1, 1))
    submission = await make_submission(db_session, exercise)

    await run_grading(db_session, submission.id, judge=judging("AC", "TLE", "WA"))

    await db_session.refresh(submission)
    assert submission.verdict == "TLE"


async def test_the_run_time_is_the_slowest_case(db_session: AsyncSession) -> None:
    """What the time limit is about is one case, not their sum."""
    exercise = await make_exercise(db_session, weights=(1, 1, 1))
    submission = await make_submission(db_session, exercise)

    await run_grading(db_session, submission.id, judge=judging("AC", "AC", "AC"))

    await db_session.refresh(submission)
    assert submission.run_time_ms == 12


async def test_memory_is_left_unknown_rather_than_guessed(
    db_session: AsyncSession,
) -> None:
    """The sandbox reports being killed for memory, never how much was used.

    A number invented here would be read as a measurement, so the column stays
    NULL until something actually measures it.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)

    await run_grading(db_session, submission.id, judge=judging("AC"))

    await db_session.refresh(submission)
    assert submission.peak_memory_mb is None


# --- What deliberately does not get written down ---------------------------


async def test_a_hidden_case_keeps_its_output_out_of_the_database(
    db_session: AsyncSession,
) -> None:
    """What a program printed on secret input describes the secret input.

    The API will not return `stdout_trunc` for a hidden case, but that is the
    second line of defence. This is the first: it is never stored.
    """
    exercise = await make_exercise(db_session, weights=(1, 1), hidden=(False, True))
    submission = await make_submission(db_session, exercise)

    await run_grading(
        db_session, submission.id, judge=judging("AC", "AC", stdout=HIDDEN_OUTPUT)
    )

    results = await results_of(db_session, submission)
    cases = {
        case.id: case
        for case in await db_session.scalars(
            select(TestCase).where(TestCase.exercise_id == exercise.id)
        )
    }
    stored = {cases[row.test_case_id].is_hidden: row.stdout_trunc for row in results}

    assert stored[False] == HIDDEN_OUTPUT
    assert stored[True] is None


async def test_stored_output_is_capped(db_session: AsyncSession) -> None:
    """A submission can print a megabyte; the row that quotes it cannot."""
    exercise = await make_exercise(db_session, hidden=(False,))
    submission = await make_submission(db_session, exercise)

    await run_grading(
        db_session,
        submission.id,
        judge=judging("WA", stdout="x" * (STORED_OUTPUT_LIMIT * 3)),
    )

    (result,) = await results_of(db_session, submission)
    assert len(result.stdout_trunc) == STORED_OUTPUT_LIMIT


# --- Failure, and whose fault it is ----------------------------------------


async def test_a_system_error_is_not_written_as_a_verdict(
    db_session: AsyncSession,
) -> None:
    """SE is our failure, and the row must not close over it.

    Writing it as a finished grading would charge the student for a broken
    daemon. The caller retries, and parks the row only when it has given up.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)

    outcome = await run_grading(
        db_session, submission.id, judge=judging("SE", message="docker is down")
    )

    assert outcome.verdict == "SE"
    await db_session.refresh(submission)
    assert submission.verdict is None
    assert submission.status != "done"
    assert await results_of(db_session, submission) == []


async def test_parking_a_submission_says_why_and_leaves_no_verdict(
    db_session: AsyncSession,
) -> None:
    """The dead letter is a row a person can find, not a log line."""
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)

    await park_submission(db_session, submission.id, "docker is down")

    await db_session.refresh(submission)
    assert submission.status == "error"
    assert submission.verdict is None
    assert submission.message == "docker is down"


async def test_a_worker_that_dies_mid_grading_leaves_the_row_saying_running(
    db_session: AsyncSession,
) -> None:
    """`running` is committed before the judging starts, on purpose.

    Otherwise a submission being graded is indistinguishable from one nobody
    has picked up, and the queue cannot be watched.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)

    def explode(code, cases, **limits):
        raise RuntimeError("worker killed")

    with pytest.raises(RuntimeError):
        await run_grading(db_session, submission.id, judge=explode)

    await db_session.refresh(submission)
    assert submission.status == "running"


async def test_a_submission_that_no_longer_exists_is_not_an_error(
    db_session: AsyncSession,
) -> None:
    """Deleting the exercise takes its submissions; a queued job outlives them."""
    assert await run_grading(db_session, uuid.uuid4(), judge=judging("AC")) is None


# --- What the judge is told -------------------------------------------------


async def test_the_judge_is_given_the_exercise_limits_and_the_cases_in_order(
    db_session: AsyncSession,
) -> None:
    exercise = await make_exercise(
        db_session, weights=(1, 1), time_limit_ms=3000, memory_limit_mb=64
    )
    submission = await make_submission(db_session, exercise, code="print(1)")
    judge = judging("AC", "AC")

    await run_grading(db_session, submission.id, judge=judge)

    assert judge.seen["code"] == "print(1)"
    assert judge.seen["time_limit_ms"] == 3000
    assert judge.seen["memory_limit_mb"] == 64
    assert judge.seen["cases"] == [(SAMPLE_INPUT, "3\n"), (SAMPLE_INPUT, "3\n")]


@pytest.mark.parametrize(
    ("time_limit_ms", "cpu_seconds"),
    [(100, 1), (999, 1), (1000, 1), (1001, 2), (2000, 2), (2500, 3), (10_000, 10)],
)
def test_a_time_limit_in_milliseconds_becomes_whole_cpu_seconds(
    time_limit_ms: int, cpu_seconds: int
) -> None:
    """RLIMIT_CPU counts seconds, so the limit rounds up -- never down.

    Rounding down would kill a correct program that was inside the limit the
    instructor set, which is the one direction this must never fail in.
    """
    assert cpu_seconds_for(time_limit_ms) == cpu_seconds


async def test_the_compiler_message_is_capped_too(db_session: AsyncSession) -> None:
    """It is read back in every page of a submission history.

    The runner's ceiling is a megabyte, which is a ceiling against a flood
    rather than a size anyone wants stored in a column and sent to a browser.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)

    await run_grading(
        db_session,
        submission.id,
        judge=judging("CE", message="x" * (STORED_OUTPUT_LIMIT * 3)),
    )

    await db_session.refresh(submission)
    assert len(submission.message) == STORED_OUTPUT_LIMIT
