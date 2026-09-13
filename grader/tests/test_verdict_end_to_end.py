"""All seven verdicts, each produced by a real submission in a real container.

The suite next door argues about the rules as values. This one is the proof
that the rules are wired to anything: for every letter a student can receive
there is a file in `tests/fixtures/` that provokes it, run through the same
path the grading worker will use. A verdict nobody has ever seen the system
produce is a verdict nobody should trust.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runner.sandbox import Limits
from runner.verdict import TestCase, Verdict, grade

pytestmark = pytest.mark.usefixtures("sandbox_images")

FIXTURES = Path(__file__).parent / "fixtures"


def submission(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# Short, so the tests that must wait for a limit wait seconds rather than a
# quarter of a minute. Same reasoning as the runner suite.
QUICK = Limits(cpu_seconds=1, startup_grace_seconds=2.0)


def test_ac_the_expected_output_exactly():
    result = grade(submission("hello.py"), [TestCase(expected="Xin chao\n")])

    assert result.verdict is Verdict.ACCEPTED
    assert [c.verdict for c in result.cases] == [Verdict.ACCEPTED]
    assert result.cases[0].stdout == "Xin chao\n"


def test_ac_the_expected_output_typed_sloppily():
    """Trailing spaces, a trailing tab, and no newline at the end. Correct."""
    result = grade(submission("sloppy_whitespace.py"), [TestCase(expected="Xin chao\nTam biet\n")])

    assert result.verdict is Verdict.ACCEPTED


def test_ac_reading_the_case_input():
    result = grade(
        submission("echo_stdin.py"),
        [TestCase(stdin="mot\nhai\n", expected="MOT\nHAI\n")],
    )

    assert result.verdict is Verdict.ACCEPTED


def test_wa_a_clean_run_with_the_wrong_answer():
    result = grade(submission("wrong_answer.py"), [TestCase(expected="Xin chao\n")])

    assert result.verdict is Verdict.WRONG_ANSWER
    assert result.cases[0].stdout == "Tam biet\n"


def test_tle_a_busy_loop():
    result = grade(submission("burn_cpu.py"), [TestCase(expected="42\n")], limits=QUICK)

    assert result.verdict is Verdict.TIME_LIMIT_EXCEEDED


def test_tle_a_program_that_uses_no_cpu_at_all():
    """The other half of the two-layer timeout, seen from the student's side.

    `sleep(3600)` never touches the CPU limit, so only the wall clock outside
    the container ends it -- and the letter must be the same either way.
    """
    result = grade(submission("sleep_forever.py"), [TestCase(expected="42\n")], limits=QUICK)

    assert result.verdict is Verdict.TIME_LIMIT_EXCEEDED


def test_mle_asking_for_more_memory_than_the_cell_has():
    result = grade(submission("eat_memory.py"), [TestCase(expected="42\n")], limits=QUICK)

    assert result.verdict is Verdict.MEMORY_LIMIT_EXCEEDED


def test_re_an_uncaught_exception_and_the_traceback_that_explains_it():
    """Runtime, not compile: this file is valid Python that fails when run.

    The traceback belongs to the student, so it comes back with the verdict.
    """
    result = grade(submission("crash.py"), [TestCase(expected="truoc khi loi\n")])

    assert result.verdict is Verdict.RUNTIME_ERROR
    assert "ValueError" in result.cases[0].stderr


def test_a_traceback_names_the_students_file_not_our_container():
    """`File "main.py", line 2` is about their program.

    `File "/sandbox/main.py", line 2` is about our mount, and it is the same
    information with a detail of our deployment stapled to it. The compile
    message already got this right; the run has to agree with it, or the two
    halves of the same submission would refer to the file by different names.
    """
    result = grade(submission("crash.py"), [TestCase(expected="truoc khi loi\n")])

    assert 'File "main.py"' in result.cases[0].stderr
    assert "/sandbox" not in result.cases[0].stderr


def test_the_graded_output_is_never_rewritten_on_the_way_out():
    """Only stderr is tidied. Stdout is the answer.

    A program that prints the mount path keeps printing it, because the moment
    we edit the text a verdict is computed from, the verdict stops being about
    what the program did.
    """
    printing_the_path = 'print("/sandbox/main.py")\n'
    result = grade(printing_the_path, [TestCase(expected="/sandbox/main.py\n")])

    assert result.verdict is Verdict.ACCEPTED
    assert result.cases[0].stdout == "/sandbox/main.py\n"


def test_re_the_right_answer_followed_by_a_crash():
    result = grade(submission("right_answer_then_crash.py"), [TestCase(expected="Xin chao\n")])

    assert result.verdict is Verdict.RUNTIME_ERROR


def test_ce_a_syntax_error_stops_the_submission_before_any_case_runs():
    """One compile, not one per test case, and no execution at all.

    The empty case list is the assertion that matters: a program that cannot
    be compiled was never run, so there is nothing to report per case, and an
    exercise with fifty test cases costs one container to reject.
    """
    result = grade(
        submission("syntax_error.py"),
        [TestCase(expected="Xin chao\n"), TestCase(expected="Xin chao\n")],
    )

    assert result.verdict is Verdict.COMPILE_ERROR
    assert result.cases == ()
    assert "SyntaxError" in result.message
    # The student's file, by the name they know it by -- not a path inside a
    # container and not a frame from the checker we wrapped around it.
    assert "main.py" in result.message
    assert "/sandbox" not in result.message


def test_se_an_image_that_was_never_built_is_our_fault():
    result = grade(
        submission("hello.py"),
        [TestCase(expected="Xin chao\n")],
        image="devpath-sandbox-nope:v1",
    )

    assert result.verdict is Verdict.SYSTEM_ERROR
    assert result.message


def test_every_case_is_run_not_just_the_ones_up_to_the_first_failure():
    """The student sees which cases failed, and partial marks need the count.

    Stopping at the first failure would be cheaper and would turn "3 of 5" --
    the thing that tells a beginner they are close -- into "failed".
    """
    result = grade(
        submission("echo_stdin.py"),
        [
            TestCase(stdin="a\n", expected="A\n"),
            TestCase(stdin="b\n", expected="WRONG\n"),
            TestCase(stdin="c\n", expected="C\n"),
        ],
    )

    assert result.verdict is Verdict.WRONG_ANSWER
    assert [c.verdict for c in result.cases] == [
        Verdict.ACCEPTED,
        Verdict.WRONG_ANSWER,
        Verdict.ACCEPTED,
    ]


def test_each_case_gets_its_own_container():
    """Nothing a submission does in one case can reach the next one.

    The same program run twice on different input must produce each answer on
    its own; a leftover process, a written file, or a warmed-up interpreter
    carrying over would make grading depend on the order of the test cases.
    """
    result = grade(
        submission("echo_stdin.py"),
        [TestCase(stdin="mot\n", expected="MOT\n"), TestCase(stdin="hai\n", expected="HAI\n")],
    )

    assert result.verdict is Verdict.ACCEPTED
    assert [c.stdout for c in result.cases] == ["MOT\n", "HAI\n"]
