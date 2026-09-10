"""Turning a finished run into one of seven letters.

No Docker here, and that is the whole point of the split: an `Execution` is
just a record of how a process ended, so every rule about what that means can
be stated as a value and checked in microseconds. The suite next door proves
the same seven letters come out of real containers running real submissions.

The rules that matter are about precedence, and each of them protects a
student from being told the wrong thing about their own program:

  * our failure is never their failure -- SE outranks everything.
  * a program stopped by a limit is not a wrong answer. It never finished, so
    its output was never the answer to anything.
  * a program that crashes after printing the right answer did not pass.
"""

from __future__ import annotations

import pytest

from runner.sandbox import Execution, Outcome
from runner.verdict import Verdict, overall, verdict_for


def ended(
    outcome: Outcome = Outcome.EXITED,
    *,
    exit_code: int | None = 0,
    stdout: str = "",
    truncated: bool = False,
    system_error: str = "",
) -> Execution:
    return Execution(
        outcome=outcome,
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        stdout_truncated=truncated,
        stderr_truncated=False,
        duration_seconds=0.1,
        image="devpath-sandbox-python:v1",
        system_error=system_error,
    )


def test_the_expected_output_printed_and_a_clean_exit_is_accepted():
    assert verdict_for(ended(stdout="42\n"), "42\n") is Verdict.ACCEPTED


def test_a_clean_exit_with_other_output_is_a_wrong_answer():
    assert verdict_for(ended(stdout="41\n"), "42\n") is Verdict.WRONG_ANSWER


def test_the_comparison_is_the_platforms_one_not_a_byte_comparison():
    """The verdict layer does not re-decide what counts as equal.

    Trailing whitespace and a missing final newline are forgiven here because
    they are forgiven in `runner.compare`, in one place, for everyone.
    """
    assert verdict_for(ended(stdout="42 "), "42\n") is Verdict.ACCEPTED


def test_output_over_the_cap_is_a_wrong_answer_even_where_it_matches():
    assert verdict_for(ended(stdout="42\n", truncated=True), "42\n") is Verdict.WRONG_ANSWER


def test_a_non_zero_exit_is_a_runtime_error():
    assert verdict_for(ended(exit_code=1), "42\n") is Verdict.RUNTIME_ERROR


def test_printing_the_right_answer_and_then_crashing_is_still_a_runtime_error():
    """The output is not the whole story about a run.

    A program that raises after printing has not solved the exercise -- it has
    written the right characters on its way to failing, and telling the
    student it passed would hide the bug they need to see.
    """
    assert verdict_for(ended(exit_code=3, stdout="42\n"), "42\n") is Verdict.RUNTIME_ERROR


@pytest.mark.parametrize(
    "outcome",
    [Outcome.CPU_TIME_EXCEEDED, Outcome.WALL_TIME_EXCEEDED],
)
def test_both_halves_of_the_timeout_are_the_same_letter_to_the_student(outcome):
    """Two mechanisms, one verdict.

    Which layer stopped the program -- the CPU limit inside the container or
    the wall clock outside it -- is an operational detail. A busy loop and a
    program asleep forever are both "too slow" to the person who wrote them.
    """
    assert verdict_for(ended(outcome, exit_code=152), "42\n") is Verdict.TIME_LIMIT_EXCEEDED


def test_a_program_killed_by_a_limit_is_never_a_wrong_answer():
    """Even when what it managed to print differs from the answer.

    It was interrupted; what it printed is a fragment, not a claim. Reporting
    WA would point the student at their logic when the problem is their
    complexity.
    """
    result = verdict_for(ended(Outcome.WALL_TIME_EXCEEDED, exit_code=137, stdout="wrong"), "42\n")
    assert result is Verdict.TIME_LIMIT_EXCEEDED


def test_running_out_of_memory_is_its_own_letter():
    killed = ended(Outcome.OUT_OF_MEMORY, exit_code=137)
    assert verdict_for(killed, "42\n") is Verdict.MEMORY_LIMIT_EXCEEDED


def test_our_own_failure_is_never_charged_to_the_student():
    """SE outranks everything, including output that happens to match.

    A daemon that is down or an image that was never built says nothing about
    the submission, and the one thing that must never happen is a student
    seeing WA for it.
    """
    broken = ended(Outcome.SYSTEM_ERROR, exit_code=None, stdout="42\n", system_error="daemon down")
    assert verdict_for(broken, "42\n") is Verdict.SYSTEM_ERROR


def test_a_submission_is_accepted_only_when_every_case_is():
    assert overall([Verdict.ACCEPTED, Verdict.ACCEPTED]) is Verdict.ACCEPTED


def test_the_first_failing_case_names_the_submission():
    """Not the worst one, the first one.

    Test cases are ordered by the instructor, easiest first, and "your third
    case timed out" is a sentence a student can act on. Ranking the letters by
    some severity of our own invention would report a later, harder case and
    bury the one they should look at.
    """
    assert overall([Verdict.ACCEPTED, Verdict.WRONG_ANSWER, Verdict.TIME_LIMIT_EXCEEDED]) is (
        Verdict.WRONG_ANSWER
    )


def test_our_failure_still_outranks_the_students_within_a_submission():
    """One case that broke on our side makes the whole submission unjudged.

    Reporting "wrong answer on case 1" when case 2 never ran would be a
    verdict we cannot stand behind: the run is incomplete, and it is our fault
    that it is.
    """
    assert overall([Verdict.WRONG_ANSWER, Verdict.SYSTEM_ERROR]) is Verdict.SYSTEM_ERROR


def test_an_exercise_with_no_test_cases_is_our_problem_not_the_students():
    """An unanswerable question. Calling it AC would hand out marks for
    nothing; calling it WA would take them away for nothing.
    """
    assert overall([]) is Verdict.SYSTEM_ERROR
