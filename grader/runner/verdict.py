"""Grade one submission: compile it once, run every test case, name a letter.

This is where the two halves below meet. `sandbox` says how a process ended
and refuses to judge it; `compare` says whether output is the expected answer
and knows nothing about processes. Neither can produce a verdict alone, and
keeping them apart is what lets the rules here be argued about in a test that
runs in microseconds while the containers are tested for what containers do.

Three rules run through everything in this module, in this order:

  * our failure is never charged to the student. SE outranks every other
    letter, in a case and across a submission.
  * a program stopped by a limit is not a wrong answer. It never finished, so
    what it printed was never its answer.
  * a program that crashed did not pass, whatever it printed on the way.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from runner.compare import outputs_match
from runner.images import PYTHON_IMAGE
from runner.sandbox import (
    COMPILE_COMMAND,
    DEFAULT_LIMITS,
    MOUNT_POINT,
    Execution,
    Limits,
    Outcome,
    execute,
)


class Verdict(StrEnum):
    """The seven letters, and the only vocabulary the rest of the platform
    needs to know about grading."""

    ACCEPTED = "AC"
    WRONG_ANSWER = "WA"
    TIME_LIMIT_EXCEEDED = "TLE"
    MEMORY_LIMIT_EXCEEDED = "MLE"
    RUNTIME_ERROR = "RE"
    COMPILE_ERROR = "CE"
    SYSTEM_ERROR = "SE"


@dataclass(frozen=True)
class TestCase:
    """One input and the answer it should produce.

    Whether a case is a sample the student may look at or a hidden one they
    may not is a decision for the layer that stores them and answers the API;
    down here every case is graded the same way.
    """

    # Not a pytest class, despite the name the domain gave it.
    __test__ = False

    stdin: str = ""
    expected: str = ""


@dataclass(frozen=True)
class CaseResult:
    verdict: Verdict
    stdout: str
    stderr: str
    duration_seconds: float
    truncated: bool
    #: Filled in only for SE: what went wrong on our side, for our logs.
    system_error: str = ""


@dataclass(frozen=True)
class Judgement:
    """What a submission got, and why.

    `cases` is empty when nothing ran -- a submission that would not compile,
    or a system that could not start a container. `message` carries the
    compiler's words or ours; it is never the place a per-case answer goes.
    """

    verdict: Verdict
    cases: tuple[CaseResult, ...] = ()
    message: str = ""


# Shown when the compile step fails without saying anything itself: killed by
# a limit rather than stopped by a syntax error.
COMPILE_GAVE_UP = "The submission could not be compiled within its limits."


def verdict_for(execution: Execution, expected: str) -> Verdict:
    """Name one run, most specific cause first.

    The order is the whole rule. Every branch above the last one is a run that
    did not finish or did not finish well, and for those the output is not
    evidence of anything -- comparing it first would report a wrong answer for
    a program that was killed halfway through printing the right one.
    """
    if execution.outcome is Outcome.SYSTEM_ERROR:
        return Verdict.SYSTEM_ERROR
    if execution.outcome is Outcome.OUT_OF_MEMORY:
        return Verdict.MEMORY_LIMIT_EXCEEDED
    if execution.outcome in (Outcome.CPU_TIME_EXCEEDED, Outcome.WALL_TIME_EXCEEDED):
        # Which layer stopped it is an operational detail. To the student who
        # wrote it, a busy loop and a program asleep forever are both too slow.
        return Verdict.TIME_LIMIT_EXCEEDED
    if execution.exit_code != 0:
        return Verdict.RUNTIME_ERROR

    matched = outputs_match(execution.stdout, expected, truncated=execution.stdout_truncated)
    return Verdict.ACCEPTED if matched else Verdict.WRONG_ANSWER


def overall(verdicts: Iterable[Verdict]) -> Verdict:
    """One letter for a whole submission.

    The first failing case names it, not the worst one: cases are ordered by
    the instructor, easiest first, and "case 3 timed out" is a sentence a
    student can act on. Ranking by some severity of our own would report a
    later, harder case and bury the one they should be looking at.
    """
    verdicts = tuple(verdicts)
    if not verdicts:
        # An exercise with no test cases is an unanswerable question, and ours
        # to fix. AC would hand out marks for nothing, WA would take them away
        # for nothing.
        return Verdict.SYSTEM_ERROR
    if Verdict.SYSTEM_ERROR in verdicts:
        # A run that broke on our side leaves the submission unjudged, even if
        # an earlier case had already failed honestly: we cannot stand behind
        # "wrong answer on case 1" when case 2 never really ran.
        return Verdict.SYSTEM_ERROR

    failed = (verdict for verdict in verdicts if verdict is not Verdict.ACCEPTED)
    return next(failed, Verdict.ACCEPTED)


def _without_the_mount_path(stderr: str) -> str:
    """Say `main.py` where Python said `/sandbox/main.py`.

    A traceback is the most useful thing a failing submission produces, and
    the student should be able to read it as being about their file. Python
    absolutises the script path since 3.11, so asking it nicely -- running
    `main.py` from a working directory set to the mount -- is not enough; the
    prefix has to come off here.

    Applied to stderr and never to stdout. Stdout is the answer being graded,
    and a verdict must not depend on us having rewritten it.
    """
    return stderr.replace(f"{MOUNT_POINT}/", "")


def run_case(
    source: str,
    case: TestCase,
    *,
    limits: Limits = DEFAULT_LIMITS,
    image: str = PYTHON_IMAGE,
) -> CaseResult:
    """Run one test case in a container of its own."""
    execution = execute(source, stdin=case.stdin, limits=limits, image=image)
    return CaseResult(
        verdict=verdict_for(execution, case.expected),
        stdout=execution.stdout,
        stderr=_without_the_mount_path(execution.stderr),
        duration_seconds=execution.duration_seconds,
        truncated=execution.stdout_truncated or execution.stderr_truncated,
        system_error=execution.system_error,
    )


def grade(
    source: str,
    cases: Sequence[TestCase],
    *,
    limits: Limits = DEFAULT_LIMITS,
    image: str = PYTHON_IMAGE,
) -> Judgement:
    """Compile once, then run every case, and say what the submission got.

    Every case gets a fresh container, so nothing one case does can reach the
    next: a leftover process, a file written to `/tmp`, or a warmed-up
    interpreter would otherwise make a verdict depend on the order the cases
    happen to run in.

    Every case is run, including those after the first failure. Stopping early
    would be cheaper and would turn "3 of 5 passed" -- the thing that tells a
    beginner they are close -- into a bare "failed".
    """
    compiled = execute(source, limits=limits, image=image, command=COMPILE_COMMAND)
    if compiled.outcome is Outcome.SYSTEM_ERROR:
        return Judgement(Verdict.SYSTEM_ERROR, message=compiled.system_error)
    if compiled.outcome is not Outcome.EXITED or compiled.exit_code != 0:
        # A compile step that ran out of time or memory says nothing itself;
        # either way the submission never became a program.
        return Judgement(Verdict.COMPILE_ERROR, message=compiled.stderr.strip() or COMPILE_GAVE_UP)

    results = tuple(run_case(source, case, limits=limits, image=image) for case in cases)
    verdict = overall(result.verdict for result in results)
    message = ""
    if verdict is Verdict.SYSTEM_ERROR:
        message = next(
            (result.system_error for result in results if result.system_error),
            "No test case could be graded.",
        )

    return Judgement(verdict, results, message)
