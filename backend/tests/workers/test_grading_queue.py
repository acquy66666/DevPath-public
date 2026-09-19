"""The wiring: which queue a job lands in, and what happens to a lost one.

Configuration rather than logic, and worth tests for exactly that reason -- a
route that quietly stops matching does not raise anything. The job simply sits
in Redis while every container reports itself healthy.
"""

import importlib
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.workers import grading as worker
from app.workers.celery_app import GRADING_QUEUE, MEDIA_QUEUE, celery_app
from app.workers.grading import CaseOutcome, cpu_seconds_for, judge

GRADER = Path(__file__).resolve().parents[3] / "grader"


def queue_for(task_name: str) -> str:
    """Where Celery would actually put this task, not what the config says."""
    return celery_app.amqp.router.route({}, task_name)["queue"].name


def test_the_grading_task_is_registered() -> None:
    """An unregistered task is only discovered when a student presses submit."""
    assert "app.workers.grading.grade_submission" in celery_app.tasks


def test_grading_and_transcoding_do_not_share_a_queue() -> None:
    """One uploaded lecture must not put every submission behind it."""
    assert queue_for("app.workers.grading.grade_submission") == GRADING_QUEUE
    assert queue_for("app.workers.video.transcode_video") == MEDIA_QUEUE


def test_a_job_survives_the_worker_that_was_running_it() -> None:
    """Grading dies by OOM reaper, which is not an exception.

    `acks_late` alone would still lose that job: without
    `task_reject_on_worker_lost` a worker killed by a signal takes its message
    with it, and the submission stays `running` forever.
    """
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_a_worker_takes_one_job_at_a_time() -> None:
    """Prefetching would hand a second submission to a worker already busy for
    seconds, behind a queue the operator sized by counting containers."""
    assert celery_app.conf.worker_prefetch_multiplier == 1


# --- The seam with the grader ----------------------------------------------


@pytest.fixture
def runner_module():
    """The grader package, which lives outside this project and is not installed.

    Skips where it is missing: this is the one test that reaches across the
    repo, and a backend checkout without it should still be able to run its own
    suite. Except under CI, which checks out the whole repo -- there a missing
    package means the seam broke, and a skip would report it as green. Same
    rule tests/conftest.py applies to Postgres.
    """
    if str(GRADER) not in sys.path:
        sys.path.insert(0, str(GRADER))
    try:
        return importlib.import_module("runner.verdict")
    except ImportError as exc:
        if os.getenv("CI"):
            raise
        pytest.skip(f"grader/runner không import được ({exc}).")


def test_the_adapter_translates_a_judgement_without_starting_a_container(
    runner_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the runner says, in the vocabulary the database speaks.

    Seconds become milliseconds and the enum becomes its letter. Both are
    conversions that look obviously right and are wrong in exactly one place,
    so they are asserted rather than assumed.
    """
    from runner.sandbox import Limits
    from runner.verdict import CaseResult, Judgement, Verdict

    seen: dict[str, object] = {}

    def fake_grade(source, cases, *, limits: Limits, **kwargs):
        seen["source"] = source
        seen["stdins"] = [case.stdin for case in cases]
        seen["limits"] = limits
        return Judgement(
            Verdict.WRONG_ANSWER,
            (
                CaseResult(
                    verdict=Verdict.ACCEPTED,
                    stdout="3\n",
                    stderr="",
                    duration_seconds=0.25,
                    truncated=False,
                ),
                CaseResult(
                    verdict=Verdict.WRONG_ANSWER,
                    stdout="4\n",
                    stderr="",
                    duration_seconds=0.5,
                    truncated=False,
                ),
            ),
        )

    monkeypatch.setattr(runner_module, "grade", fake_grade)

    outcome = judge(
        "print(3)",
        [("1 2\n", "3\n"), ("2 2\n", "4\n")],
        time_limit_ms=2500,
        memory_limit_mb=64,
    )

    assert outcome.verdict == "WA"
    assert outcome.cases == (
        CaseOutcome(verdict="AC", run_time_ms=250, stdout="3\n"),
        CaseOutcome(verdict="WA", run_time_ms=500, stdout="4\n"),
    )
    assert seen["source"] == "print(3)"
    assert seen["stdins"] == ["1 2\n", "2 2\n"]


def test_the_exercise_sets_only_the_limits_that_are_its_business(
    runner_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Time and memory are a teaching decision; the rest are not.

    Process count, tmpfs size and the output cap keep one submission from
    affecting the next one, so they stay at the platform's values whatever an
    instructor typed into the form.
    """
    from runner.sandbox import DEFAULT_LIMITS

    captured: dict[str, object] = {}

    def fake_grade(source, cases, *, limits, **kwargs):
        captured["limits"] = limits
        from runner.verdict import Judgement, Verdict

        return Judgement(Verdict.ACCEPTED)

    monkeypatch.setattr(runner_module, "grade", fake_grade)

    judge("print(3)", [], time_limit_ms=2500, memory_limit_mb=64)
    limits = captured["limits"]

    assert limits.cpu_seconds == cpu_seconds_for(2500)
    assert limits.memory_mb == 64
    assert limits.pids == DEFAULT_LIMITS.pids
    assert limits.tmpfs_mb == DEFAULT_LIMITS.tmpfs_mb
    assert limits.output_bytes == DEFAULT_LIMITS.output_bytes
    assert limits.cpus == DEFAULT_LIMITS.cpus


# --- Retry, and giving up ---------------------------------------------------


class StubTask:
    """Enough of a Celery task to ask it the only question that matters."""

    def __init__(self, retries: int, max_retries: int = 2) -> None:
        self.request = SimpleNamespace(retries=retries)
        self.max_retries = max_retries
        self.asked_for = None

    def retry(self, *, countdown, exc):
        self.asked_for = (countdown, exc)
        # The real one raises; ours is raised by the caller, so hand it back.
        return RuntimeError("retry")


def test_a_system_error_is_tried_again_before_anyone_is_told(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parked = []
    monkeypatch.setattr(worker, "park", lambda *args: parked.append(args))
    task = StubTask(retries=0)

    with pytest.raises(RuntimeError):
        worker._retry_or_park(task, uuid.uuid4(), "docker is down")

    countdown, _ = task.asked_for
    assert countdown == worker.RETRY_DELAY_SECONDS
    assert parked == []


def test_the_wait_grows_between_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The failures worth retrying are a daemon restarting or a host briefly
    out of memory. Hammering either turns a hiccup into an outage."""
    monkeypatch.setattr(worker, "park", lambda *args: None)
    task = StubTask(retries=1)

    with pytest.raises(RuntimeError):
        worker._retry_or_park(task, uuid.uuid4(), "docker is down")

    countdown, _ = task.asked_for
    assert countdown == worker.RETRY_DELAY_SECONDS * 2


def test_the_last_attempt_parks_the_row_instead_of_retrying_forever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dead letter. A queue with no end to its retries is a queue that
    grows while every attempt fails the same way."""
    parked = []
    monkeypatch.setattr(worker, "park", lambda *args: parked.append(args))
    task = StubTask(retries=2)
    submission_id = uuid.uuid4()

    assert worker._retry_or_park(task, submission_id, "docker is down") == "error"

    assert task.asked_for is None
    assert parked == [(submission_id, worker.GAVE_UP_MESSAGE)]


def test_the_student_is_not_shown_the_technical_reason() -> None:
    """`message` is read by a learner. "bind source path does not exist" sends
    them to reread correct code; the log is where that sentence belongs."""
    assert "docker" not in worker.GAVE_UP_MESSAGE.lower()
    assert "Hệ thống chấm bài" in worker.GAVE_UP_MESSAGE


def test_a_job_for_a_finished_submission_is_neither_retried_nor_parked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A redelivered job is the end of the story, not a failure.

    `run_grading` answers it with `AlreadyFinished` (see test_grading.py). If
    the task read that as trouble, the retries would end in `park`, which is
    exactly the write that erases a verdict.
    """

    async def already_done(session, submission_id):
        return worker.AlreadyFinished("done")

    async def without_a_database(work):
        return await work(None)

    gave_up = []
    monkeypatch.setattr(worker, "run_grading", already_done)
    monkeypatch.setattr(worker, "_with_session", without_a_database)
    monkeypatch.setattr(worker, "_retry_or_park", lambda *args: gave_up.append(args))

    assert worker.grade_submission.run(str(uuid.uuid4())) == "already done"
    assert gave_up == []
