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
from unittest import mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonProgress,
    Submission,
    SubmissionResult,
    TestCase,
    User,
)
from app.schemas.grading import GradingCaseEvent, GradingEvent
from app.services import grading_events
from app.workers.grading import (
    STORED_OUTPUT_LIMIT,
    CaseOutcome,
    CaseProgress,
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
    session: AsyncSession,
    exercise: CodeExercise,
    *,
    code: str = "print(3)",
    is_trial: bool = False,
    enrolled: bool = True,
) -> Submission:
    student = User(
        email=f"hv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Học viên",
        password_hash="x",
        role="student",
    )
    session.add(student)
    await session.flush()

    # Enrolled by default because that is the only way to reach the page that
    # submits. `enrolled=False` is the instructor trying their own exercise:
    # graded like anybody's, but with no progress to record.
    if enrolled:
        session.add(
            Enrollment(user_id=student.id, course_id=await course_of(session, exercise))
        )
        await session.flush()

    submission = Submission(
        user_id=student.id,
        exercise_id=exercise.id,
        code=code,
        language="python",
        status="pending",
        is_trial=is_trial,
    )
    session.add(submission)
    await session.flush()
    return submission


def judging(*verdicts: str, stdout: str = "3\n", message: str = "") -> object:
    """A judge that hands back the verdicts it was built with.

    It calls `on_case` between cases the way the real one does, so a test can
    watch what is announced *while* a submission is being graded rather than
    only what is left behind at the end.
    """

    def judge(code, cases, *, time_limit_ms, memory_limit_mb, on_case=None):
        judge.seen = {
            "code": code,
            "cases": list(cases),
            "time_limit_ms": time_limit_ms,
            "memory_limit_mb": memory_limit_mb,
        }
        for index, verdict in enumerate(verdicts):
            # A compile error never reaches a test case, so a judge built to
            # report one does not pretend to have run any.
            if on_case is not None and verdict != "CE":
                on_case(CaseProgress(index=index, verdict=verdict, run_time_ms=10 + index))
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


# --- What is said while it happens -----------------------------------------


class Recorder:
    """Collects announcements instead of publishing them."""

    def __init__(self) -> None:
        self.events: list[GradingEvent] = []

    def __call__(self, event: GradingEvent) -> None:
        self.events.append(event)

    def statuses(self) -> list[str]:
        return [event.status for event in self.events]


async def test_progress_is_announced_per_case_as_the_run_goes(
    db_session: AsyncSession,
) -> None:
    """The point of the whole channel: a count that moves before the end.

    Three cases must produce three progress events, not one summary at the
    finish -- a progress bar that only ever shows 0% and then 100% is a
    spinner with extra machinery behind it.
    """
    exercise = await make_exercise(db_session, weights=(1, 1, 1))
    submission = await make_submission(db_session, exercise)
    announce = Recorder()

    await run_grading(
        db_session, submission.id, judge=judging("AC", "WA", "AC"), announce=announce
    )

    assert announce.statuses() == ["running", "running", "running", "running", "done"]
    ticks = [event for event in announce.events if event.case is not None]
    assert [tick.completed_cases for tick in ticks] == [1, 2, 3]
    assert [tick.case.verdict for tick in ticks] == ["AC", "WA", "AC"]
    assert all(tick.total_cases == 3 for tick in announce.events[:-1])


async def test_the_first_announcement_says_how_many_cases_there_are(
    db_session: AsyncSession,
) -> None:
    """`running` arrives before any case does, carrying the denominator.

    Without it the page can say "test 1" but not "test 1/10", and the number
    it is missing is the one that tells a student whether to keep waiting.
    """
    exercise = await make_exercise(db_session, weights=(1, 1, 1, 1))
    submission = await make_submission(db_session, exercise)
    announce = Recorder()

    await run_grading(
        db_session,
        submission.id,
        judge=judging("AC", "AC", "AC", "AC"),
        announce=announce,
    )

    first = announce.events[0]
    assert first.status == "running"
    assert first.total_cases == 4
    assert first.completed_cases == 0
    assert first.case is None


async def test_the_last_announcement_carries_the_verdict_and_the_score(
    db_session: AsyncSession,
) -> None:
    exercise = await make_exercise(db_session, weights=(1, 1))
    submission = await make_submission(db_session, exercise)
    announce = Recorder()

    await run_grading(
        db_session, submission.id, judge=judging("AC", "WA"), announce=announce
    )

    last = announce.events[-1]
    assert last.status == "done"
    assert last.is_terminal
    assert last.verdict == "WA"
    assert last.score == 50


async def test_no_announcement_carries_what_a_program_printed(
    db_session: AsyncSession,
) -> None:
    """The structural half of the hidden-test-case rule, on the live channel.

    The judge below prints the secret on every case, hidden and sample alike.
    Not one event may contain it -- and the reason no conditional is needed to
    achieve that is that `GradingEvent` has no field for output at all.
    """
    exercise = await make_exercise(db_session, weights=(1, 1), hidden=(False, True))
    submission = await make_submission(db_session, exercise)
    announce = Recorder()

    await run_grading(
        db_session,
        submission.id,
        judge=judging("WA", "WA", stdout=HIDDEN_OUTPUT),
        announce=announce,
    )

    published = [event.model_dump_json() for event in announce.events]
    assert published, "nothing was announced at all"
    assert not any(HIDDEN_OUTPUT in line for line in published)
    assert "stdout" not in GradingEvent.model_fields
    assert "stdout" not in GradingCaseEvent.model_fields


async def test_a_case_event_says_which_case_by_position_not_by_arrival(
    db_session: AsyncSession,
) -> None:
    """Position comes from the row, so a reordered exercise still lines up."""
    exercise = await make_exercise(db_session, weights=(1, 1), hidden=(False, True))
    submission = await make_submission(db_session, exercise)
    announce = Recorder()

    await run_grading(
        db_session, submission.id, judge=judging("AC", "AC"), announce=announce
    )

    ticks = [event.case for event in announce.events if event.case is not None]
    assert [tick.position for tick in ticks] == [0, 1]
    assert [tick.is_hidden for tick in ticks] == [False, True]


async def test_a_system_error_announces_nothing_terminal(
    db_session: AsyncSession,
) -> None:
    """Our failure does not end anyone's wait, because it is about to be retried.

    A `done` here would stop the page on an attempt that is being tried again
    a few seconds later, and the student would be shown a failure that the
    platform itself does not consider final.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)
    announce = Recorder()

    await run_grading(db_session, submission.id, judge=judging("SE"), announce=announce)

    assert not any(event.is_terminal for event in announce.events)


async def test_parking_a_submission_ends_the_wait(db_session: AsyncSession) -> None:
    """Giving up is terminal, and the channel has to say so.

    Otherwise the only thing that ends a socket over a parked submission is
    the five-minute deadline, and the student watches a spinner through it.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)
    announce = Recorder()

    await park_submission(db_session, submission.id, "docker is down", announce=announce)

    assert [event.status for event in announce.events] == ["error"]
    assert announce.events[0].is_terminal


async def test_grading_survives_a_publisher_that_throws(
    db_session: AsyncSession,
) -> None:
    """Telemetry is not allowed to fail a submission.

    `run_grading` does not catch this itself -- `publish_event` does, which is
    the single place where a broken channel becomes a log line. The test runs
    with the real announcer and a publisher that throws on every call, so it
    proves the seam is where it is claimed to be rather than that a fake was
    polite.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)

    class Broken:
        def publish(self, event: GradingEvent) -> None:
            raise RuntimeError("redis is down")

    with mock.patch.object(grading_events, "get_publisher", Broken):
        await run_grading(db_session, submission.id, judge=judging("AC"))

    await db_session.refresh(submission)
    assert submission.status == "done"
    assert submission.verdict == "AC"


# --- Trial runs -------------------------------------------------------------


HIDDEN_ANSWER = "ANSWER-KEY-OF-A-HIDDEN-CASE"


async def test_a_trial_run_is_never_handed_a_hidden_case(
    db_session: AsyncSession,
) -> None:
    """The strongest form of the rule, and the reason trials filter at load.

    The judge records everything it was given. A trial run must not have the
    hidden case's input or expected output anywhere in that record -- not
    stripped from the results afterwards, but never fetched. There is no
    moment in the process at which a trial run holds an answer key.
    """
    exercise = await make_exercise(db_session, weights=(1, 1), hidden=(False, True))
    cases = await db_session.scalars(
        select(TestCase).where(TestCase.exercise_id == exercise.id)
    )
    for case in cases:
        if case.is_hidden:
            case.expected_output = HIDDEN_ANSWER
    await db_session.flush()

    submission = await make_submission(db_session, exercise, is_trial=True)
    judge = judging("AC")

    await run_grading(db_session, submission.id, judge=judge)

    handed_over = repr(judge.seen["cases"])
    assert HIDDEN_ANSWER not in handed_over
    assert len(judge.seen["cases"]) == 1


async def test_a_real_submission_still_gets_every_case(
    db_session: AsyncSession,
) -> None:
    """The control. Without it the test above would pass on a worker that had
    stopped grading anything at all."""
    exercise = await make_exercise(db_session, weights=(1, 1), hidden=(False, True))
    submission = await make_submission(db_session, exercise)
    judge = judging("AC", "AC")

    await run_grading(db_session, submission.id, judge=judge)

    assert len(judge.seen["cases"]) == 2


async def test_a_trial_run_counts_only_the_cases_it_will_run(
    db_session: AsyncSession,
) -> None:
    """"Test 1/1", not "test 1/3": the denominator describes this run."""
    exercise = await make_exercise(
        db_session, weights=(1, 1, 1), hidden=(False, True, True)
    )
    submission = await make_submission(db_session, exercise, is_trial=True)
    announce = Recorder()

    await run_grading(
        db_session, submission.id, judge=judging("AC"), announce=announce
    )

    assert announce.events[0].total_cases == 1
    assert all(event.total_cases == 1 for event in announce.events)


async def test_a_trial_run_scores_against_the_samples_it_ran(
    db_session: AsyncSession,
) -> None:
    """Half the sample cases passing is 50, even though the exercise has more.

    A trial that scored out of the whole exercise would tell a student their
    correct solution was worth a third of the marks.
    """
    exercise = await make_exercise(
        db_session, weights=(1, 1, 1, 1), hidden=(False, False, True, True)
    )
    submission = await make_submission(db_session, exercise, is_trial=True)

    await run_grading(db_session, submission.id, judge=judging("AC", "WA"))

    await db_session.refresh(submission)
    assert submission.score == 50
    assert submission.verdict == "WA"


# --- Solving the exercise finishes the lesson -------------------------------


async def course_of(session: AsyncSession, exercise: CodeExercise) -> uuid.UUID:
    """The course an exercise belongs to, the long way round the curriculum."""
    return await session.scalar(
        select(CourseSection.course_id)
        .join(Lesson, Lesson.section_id == CourseSection.id)
        .where(Lesson.id == exercise.lesson_id)
    )


async def completion_of(
    session: AsyncSession, submission: Submission, exercise: CodeExercise
) -> LessonProgress | None:
    return await session.scalar(
        select(LessonProgress)
        .join(Enrollment, Enrollment.id == LessonProgress.enrollment_id)
        .where(
            Enrollment.user_id == submission.user_id,
            LessonProgress.lesson_id == exercise.lesson_id,
        )
    )


async def test_an_accepted_submission_finishes_its_lesson(
    db_session: AsyncSession,
) -> None:
    """Solving the exercise is finishing the lesson; nobody should have to say so.

    A student who gets AC and then has to tick "đánh dấu hoàn thành" by hand is
    being asked to tell the system something it just watched happen.
    """
    exercise = await make_exercise(db_session, weights=(1, 1))
    submission = await make_submission(db_session, exercise)

    await run_grading(db_session, submission.id, judge=judging("AC", "AC"))

    progress = await completion_of(db_session, submission, exercise)
    assert progress is not None
    assert progress.completed_at is not None


async def test_finishing_the_only_lesson_finishes_the_course(
    db_session: AsyncSession,
) -> None:
    """The enrolment's own completion is computed, so it has to follow along."""
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)

    await run_grading(db_session, submission.id, judge=judging("AC"))

    enrollment = await db_session.scalar(
        select(Enrollment).where(Enrollment.user_id == submission.user_id)
    )
    assert enrollment is not None
    assert enrollment.completed_at is not None


async def test_a_wrong_answer_leaves_the_lesson_unfinished(
    db_session: AsyncSession,
) -> None:
    exercise = await make_exercise(db_session, weights=(1, 1))
    submission = await make_submission(db_session, exercise)

    await run_grading(db_session, submission.id, judge=judging("AC", "WA"))

    progress = await completion_of(db_session, submission, exercise)
    assert progress is None or progress.completed_at is None


async def test_a_trial_run_never_finishes_the_lesson(
    db_session: AsyncSession,
) -> None:
    """Passing the samples is not solving the exercise -- that is what hidden
    cases are for, and a rehearsal that completed the lesson would hand the
    tick to code that has not met them."""
    exercise = await make_exercise(db_session, weights=(1, 1), hidden=(False, True))
    submission = await make_submission(db_session, exercise, is_trial=True)

    await run_grading(db_session, submission.id, judge=judging("AC"))

    await db_session.refresh(submission)
    assert submission.verdict == "AC"
    progress = await completion_of(db_session, submission, exercise)
    assert progress is None or progress.completed_at is None


async def test_a_second_accepted_submission_keeps_the_first_completion_time(
    db_session: AsyncSession,
) -> None:
    """Solving it again does not move the day it was solved."""
    exercise = await make_exercise(db_session)
    first = await make_submission(db_session, exercise)
    await run_grading(db_session, first.id, judge=judging("AC"))
    progress = await completion_of(db_session, first, exercise)
    assert progress is not None
    finished_at = progress.completed_at

    again = Submission(
        user_id=first.user_id,
        exercise_id=exercise.id,
        code="print(3)",
        language="python",
        status="pending",
    )
    db_session.add(again)
    await db_session.flush()
    await run_grading(db_session, again.id, judge=judging("AC"))

    await db_session.refresh(progress)
    assert progress.completed_at == finished_at


async def test_grading_still_works_for_somebody_with_no_enrolment(
    db_session: AsyncSession,
) -> None:
    """An instructor trying their own exercise is graded and leaves no progress.

    Progress belongs to an enrolment, and inventing one here would put the
    author of a course into their own completion figures.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise, enrolled=False)

    outcome = await run_grading(db_session, submission.id, judge=judging("AC"))

    assert outcome.verdict == "AC"
    await db_session.refresh(submission)
    assert submission.status == "done"
    assert await completion_of(db_session, submission, exercise) is None


# --- The same job, delivered twice ------------------------------------------
#
# The queue acknowledges a grading job only after it finishes, and redelivers
# it when the worker running it dies (`task_acks_late` + `task_reject_on_worker
# _lost`). A worker that dies *after* committing the verdict but *before* the
# ack is therefore followed by a second delivery of a job that is already done.
# Grading it again used to re-mark the row `running` -- which the verdict it
# already carries forbids (`ck_submissions_verdict_requires_done`) -- so every
# attempt failed on its first commit, the retries ran out, and the submission
# was parked as `error`: the one write that is allowed to clear a verdict,
# erasing one the student had already been shown.


def never_called(code, cases, **limits):
    raise AssertionError("a finished submission must not be judged again")


async def test_a_job_delivered_again_after_grading_leaves_the_result_alone(
    db_session: AsyncSession,
) -> None:
    exercise = await make_exercise(db_session, weights=(1, 1))
    submission = await make_submission(db_session, exercise)
    await run_grading(db_session, submission.id, judge=judging("AC", "AC"))

    await run_grading(db_session, submission.id, judge=never_called)

    await db_session.refresh(submission)
    assert submission.status == "done"
    assert submission.verdict == "AC"
    assert submission.score == 100
    assert len(await results_of(db_session, submission)) == 2


async def test_a_job_delivered_again_ends_the_wait_again(
    db_session: AsyncSession,
) -> None:
    """The first `done` may have gone out to nobody -- pub/sub keeps no copy.

    A page that connected between the two deliveries is waiting for an event
    that was already spent, so the second delivery repeats it from the row.
    """
    exercise = await make_exercise(db_session, weights=(1, 1))
    submission = await make_submission(db_session, exercise)
    await run_grading(db_session, submission.id, judge=judging("AC", "WA"))
    announce = Recorder()

    await run_grading(db_session, submission.id, judge=never_called, announce=announce)

    assert [event.status for event in announce.events] == ["done"]
    assert announce.events[0].verdict == "WA"
    assert announce.events[0].score == 50


async def test_a_job_delivered_again_after_being_parked_stays_parked(
    db_session: AsyncSession,
) -> None:
    """Giving up is final too: a parked row is not quietly re-attempted."""
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)
    await park_submission(db_session, submission.id, "docker is down")
    announce = Recorder()

    await run_grading(db_session, submission.id, judge=never_called, announce=announce)

    await db_session.refresh(submission)
    assert submission.status == "error"
    assert [event.status for event in announce.events] == ["error"]


async def test_a_job_delivered_again_after_a_worker_died_mid_run_is_graded(
    db_session: AsyncSession,
) -> None:
    """`running` is the one unfinished state a redelivery must still grade.

    It is what a worker killed halfway leaves behind, and results are written
    in the same commit as the verdict, so a `running` row has none to collide
    with.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)
    submission.status = "running"
    await db_session.commit()

    await run_grading(db_session, submission.id, judge=judging("AC"))

    await db_session.refresh(submission)
    assert submission.status == "done"
    assert submission.verdict == "AC"


async def test_parking_never_erases_a_verdict(db_session: AsyncSession) -> None:
    """The last line of defence, for a retry that gives up after a success.

    Whatever route leads to `park_submission` for a submission that has
    already been judged, the judgement is the thing to keep.
    """
    exercise = await make_exercise(db_session)
    submission = await make_submission(db_session, exercise)
    await run_grading(db_session, submission.id, judge=judging("AC"))
    announce = Recorder()

    await park_submission(db_session, submission.id, "docker is down", announce=announce)

    await db_session.refresh(submission)
    assert submission.status == "done"
    assert submission.verdict == "AC"
    assert submission.message != "docker is down"
    assert announce.events == []
