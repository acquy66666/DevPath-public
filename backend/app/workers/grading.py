"""Grading one submission: from a pending row to a verdict.

Three layers meet here and each keeps its own job:

* `grader/runner` starts containers and judges. It knows nothing about the
  database and is not imported until a submission is actually being graded.
* `run_grading()` is everything this platform decides -- what the score means,
  what is written down, what is deliberately not. It takes the judging
  function as an argument, so it is tested in milliseconds against a fake.
* the Celery task at the bottom owns the event loop, the retries, and the
  decision to give up.

Two rules from the sandbox checklist show up as code rather than as comments:

  **Our failure is never charged to the student.** A system error is not
  written as a verdict. It is retried, and if it keeps failing the row is
  parked with the reason -- unjudged, not failed.

  **A hidden test case never leaves the server.** The output of a hidden case
  is not stored at all. The API already refuses to return it; this is the line
  before that one, because a column that is never filled cannot be leaked by
  an endpoint written later.
"""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models import CodeExercise, Submission, SubmissionResult, TestCase
from app.workers.celery_app import celery_app

# How much of a sample case's output is kept. Enough to show a student what
# their program printed instead of the answer, far too little to be a place to
# store a file: the run itself is already capped at 1 MB, and every byte past
# the first screenful is one nobody reads and everybody backs up.
STORED_OUTPUT_LIMIT = 2000

# Only a system error is retried, so the ceiling is low: two more attempts
# cover a daemon restarting or a host briefly out of memory, and anything that
# survives them is a broken deployment that a third attempt will not fix.
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 15

# The message a student sees when we have given up. It says whose fault it is,
# because the alternative is a learner rereading correct code.
GAVE_UP_MESSAGE = (
    "Hệ thống chấm bài đang gặp sự cố. Bài của bạn chưa được chấm — "
    "vui lòng nộp lại sau ít phút."
)

SYSTEM_ERROR = "SE"

# The technical reason goes here and nowhere near the student. Submitted code
# is never logged: it is a stranger's file, and a shared log is the one place
# it would be read without any of the precautions the sandbox takes.
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaseOutcome:
    """What one test case did, in this layer's vocabulary."""

    verdict: str
    run_time_ms: int
    stdout: str = ""


@dataclass(frozen=True)
class GradingOutcome:
    verdict: str
    message: str = ""
    cases: tuple[CaseOutcome, ...] = ()


Judge = Callable[..., GradingOutcome]


def cpu_seconds_for(time_limit_ms: int) -> int:
    """The instructor's milliseconds as a whole CPU second, rounded up.

    `RLIMIT_CPU` counts seconds and nothing finer, so the limit can only be
    rounded -- and only upwards. Rounding down would kill a program that was
    inside the limit its author was told about, which is the one direction
    this must never fail in. A generous limit costs a few seconds of a worker;
    a mean one fails correct code.
    """
    return max(1, math.ceil(time_limit_ms / 1000))


def judge(
    code: str,
    cases: Sequence[tuple[str, str]],
    *,
    time_limit_ms: int,
    memory_limit_mb: int,
) -> GradingOutcome:
    """Hand the submission to the sandbox and translate what comes back.

    The import is here rather than at module scope on purpose: the grader
    lives outside this package and needs a Docker daemon, so an API container
    that only ever enqueues must not need either to start. It also keeps the
    seam narrow -- this function is the only place in the backend that knows
    the runner's types exist.
    """
    from runner.sandbox import DEFAULT_LIMITS, Limits
    from runner.verdict import TestCase as RunnerCase
    from runner.verdict import grade

    limits = Limits(
        cpu_seconds=cpu_seconds_for(time_limit_ms),
        memory_mb=memory_limit_mb,
        # Everything else is platform-wide and not an instructor's decision:
        # they keep one submission from affecting the next one.
        cpus=DEFAULT_LIMITS.cpus,
        pids=DEFAULT_LIMITS.pids,
        tmpfs_mb=DEFAULT_LIMITS.tmpfs_mb,
        output_bytes=DEFAULT_LIMITS.output_bytes,
    )

    judgement = grade(
        code,
        [RunnerCase(stdin=stdin, expected=expected) for stdin, expected in cases],
        limits=limits,
    )

    return GradingOutcome(
        verdict=str(judgement.verdict),
        message=judgement.message,
        cases=tuple(
            CaseOutcome(
                verdict=str(result.verdict),
                run_time_ms=int(result.duration_seconds * 1000),
                stdout=result.stdout,
            )
            for result in judgement.cases
        ),
    )


async def _cases_of(session: AsyncSession, exercise_id: uuid.UUID) -> list[TestCase]:
    rows = await session.scalars(
        select(TestCase)
        .where(TestCase.exercise_id == exercise_id)
        .order_by(TestCase.position)
    )
    return list(rows)


async def run_grading(
    session: AsyncSession, submission_id: uuid.UUID, *, judge: Judge = judge
) -> GradingOutcome | None:
    """Grade one submission and write down everything except a system error.

    Returns what the judge said, or None when the submission is gone -- a job
    can outlive the row that queued it, and an exercise deleted mid-grading
    takes its submissions with it. That is not a failure and must not be
    retried.
    """
    submission = await session.get(Submission, submission_id)
    if submission is None:
        return None

    # Committed before any judging starts: otherwise a submission being graded
    # looks exactly like one nobody has picked up, and a worker killed halfway
    # leaves no trace of having tried.
    submission.status = "running"
    await session.commit()

    exercise = await session.get(CodeExercise, submission.exercise_id)
    if exercise is None:
        return None

    cases = await _cases_of(session, exercise.id)

    outcome = judge(
        submission.code,
        [(case.input, case.expected_output) for case in cases],
        time_limit_ms=exercise.time_limit_ms,
        memory_limit_mb=exercise.memory_limit_mb,
    )

    if outcome.verdict == SYSTEM_ERROR:
        # Nothing is written: the row stays `running` and the caller decides
        # whether to try again or park it. A verdict here would close the
        # submission over a failure that was ours.
        return outcome

    _record(session, submission, cases, outcome)
    await session.commit()
    return outcome


def _record(
    session: AsyncSession,
    submission: Submission,
    cases: Sequence[TestCase],
    outcome: GradingOutcome,
) -> None:
    """Fill in the submission and one row per case that actually ran.

    A compile error has no per-case results -- the program never became a
    program -- so the compiler's words go in `message` and no rows are
    written.
    """
    total_weight = sum(case.score_weight for case in cases)
    passed_weight = 0
    slowest = 0

    for case, result in zip(cases, outcome.cases, strict=False):
        if result.verdict == "AC":
            passed_weight += case.score_weight
        slowest = max(slowest, result.run_time_ms)

        session.add(
            SubmissionResult(
                submission_id=submission.id,
                test_case_id=case.id,
                verdict=result.verdict,
                run_time_ms=result.run_time_ms,
                # The whole rule, in one conditional: a hidden case's output is
                # not stored, so no endpoint can return it by accident.
                stdout_trunc=(
                    None if case.is_hidden else result.stdout[:STORED_OUTPUT_LIMIT]
                ),
            )
        )

    submission.status = "done"
    submission.verdict = outcome.verdict
    submission.score = (
        round(100 * passed_weight / total_weight) if total_weight else 0
    )
    submission.run_time_ms = slowest or None
    # Deliberately not filled: the sandbox reports being killed for memory, and
    # never how much was used. A number invented here would be read as a
    # measurement.
    submission.peak_memory_mb = None
    # Capped like the per-case output, and for the same reason: the compiler's
    # words arrive through the sandbox's 1 MB ceiling, and this column is read
    # back in every page of a student's submission history.
    submission.message = outcome.message[:STORED_OUTPUT_LIMIT] or None


async def park_submission(
    session: AsyncSession, submission_id: uuid.UUID, reason: str
) -> None:
    """Give up on a submission, in writing.

    This is the dead letter, and it is a row rather than a queue: Redis has no
    place to put a message nobody could process, and a log line is not
    something a student or an instructor can see. `error` is its own status,
    so the row is findable -- and it carries no verdict, because nothing was
    judged.
    """
    submission = await session.get(Submission, submission_id)
    if submission is None:
        return

    submission.status = "error"
    submission.verdict = None
    submission.message = reason
    await session.commit()


async def _with_session(work: Callable[[AsyncSession], Awaitable[object]]) -> object:
    # A fresh engine per task: the worker is sync, so there is no long-lived
    # loop for a pooled connection to belong to.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await work(session)
    finally:
        await engine.dispose()


def park(submission_id: uuid.UUID, message: str) -> None:
    """The blocking half of `park_submission`, so the retry rule can be tested
    without a database and the writing tested without Celery."""
    asyncio.run(_with_session(lambda s: park_submission(s, submission_id, message)))


class GradingUnavailable(RuntimeError):
    """The grader could not judge this submission, and it is not the code's fault."""


@celery_app.task(
    bind=True,
    name="app.workers.grading.grade_submission",
    max_retries=MAX_RETRIES,
)
def grade_submission(self, submission_id: str) -> str:
    """Celery entry point. Owns the event loop, the retries, and giving up.

    Only a system error is retried. A wrong answer, a crash and a compile
    error are answers about the submitted code -- running them again would
    produce the same answer at three times the cost.
    """
    identifier = uuid.UUID(submission_id)

    try:
        outcome = asyncio.run(_with_session(lambda s: run_grading(s, identifier)))
    except Exception as exc:
        # A broken worker, not a bad submission: the same treatment as SE.
        return _retry_or_park(self, identifier, f"{type(exc).__name__}: {exc}")

    if outcome is None:
        return "missing"
    if outcome.verdict == SYSTEM_ERROR:
        return _retry_or_park(self, identifier, outcome.message)
    return outcome.verdict


def _retry_or_park(task, submission_id: uuid.UUID, reason: str) -> str:
    """Try again, or write the failure down where someone will see it.

    The delay grows between attempts: the failures worth retrying are a daemon
    restarting or a host briefly out of memory, and hammering either of them
    is how a queue turns a hiccup into an outage.
    """
    logger.warning(
        "grading failed for submission %s (attempt %s): %s",
        submission_id,
        task.request.retries + 1,
        reason,
    )

    if task.request.retries < task.max_retries:
        raise task.retry(
            countdown=RETRY_DELAY_SECONDS * (2**task.request.retries),
            exc=GradingUnavailable(reason),
        )

    logger.error("giving up on submission %s: %s", submission_id, reason)
    park(submission_id, GAVE_UP_MESSAGE)
    return "error"
