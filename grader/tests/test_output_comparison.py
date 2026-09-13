"""What counts as the right answer, and what is only a difference in typing.

These are grading rules, not container rules: no Docker, no submission, no
program. That is the point of keeping them in their own module -- every one of
the judgements below can be argued about, changed, and re-tested in
milliseconds, while the container tests next door take a minute and prove
something else entirely.

The rule being drawn here has two sides. A student must not lose a test case
over a trailing space or over the newline their editor did or did not put at
the end of the file. And a student must not pass one by printing something
that merely looks close: everything inside a line, blank lines between lines,
and the order of it all still have to be right.
"""

from __future__ import annotations

import pytest

from runner.compare import normalize, outputs_match


def test_the_same_text_matches_itself():
    assert outputs_match("42\n", "42\n") is True


def test_a_missing_final_newline_does_not_fail_a_correct_answer():
    """`print` adds one, `sys.stdout.write` does not, and neither is wrong.

    This is the single most common way a correct program is marked wrong by a
    judge that compares raw bytes, and it teaches nothing.
    """
    assert outputs_match("42", "42\n") is True
    assert outputs_match("42\n", "42") is True


def test_extra_blank_lines_at_the_end_are_ignored():
    assert outputs_match("42\n\n\n", "42\n") is True
    assert outputs_match("42\n   \n\t\n", "42\n") is True


def test_trailing_spaces_and_tabs_on_a_line_are_ignored():
    """A loop that prints "value " for each item is the usual source.

    The alternative is a student staring at two identical-looking lines,
    which is a puzzle about our comparator rather than about their code.
    """
    assert outputs_match("1 2 3 \n", "1 2 3\n") is True
    assert outputs_match("a\t\nb  \n", "a\nb\n") is True


def test_windows_line_endings_match_unix_ones_in_either_direction():
    """The carriage return can come from either side.

    From the student's, if their program writes in text mode on Windows; from
    the instructor's, if they pasted the expected output from an editor that
    saves CRLF. Neither is a wrong answer.
    """
    assert outputs_match("mot\r\nhai\r\n", "mot\nhai\n") is True
    assert outputs_match("mot\nhai\n", "mot\r\nhai\r\n") is True


def test_an_output_of_only_whitespace_matches_an_expected_output_of_nothing():
    assert outputs_match("\n\n  \n", "") is True
    assert outputs_match("", "") is True


def test_leading_whitespace_is_part_of_the_answer():
    """Indentation is output for a whole class of exercises -- pyramids,
    trees, formatted tables. Stripping both ends of a line would silently
    stop grading half of what those exercises ask for.
    """
    assert outputs_match("  42\n", "42\n") is False


def test_spacing_inside_a_line_is_part_of_the_answer():
    assert outputs_match("1  2\n", "1 2\n") is False


def test_a_blank_line_in_the_middle_is_part_of_the_answer():
    assert outputs_match("a\nb\n", "a\n\nb\n") is False


def test_the_answer_is_case_sensitive():
    assert outputs_match("Yes\n", "yes\n") is False


def test_lines_in_the_wrong_order_are_wrong():
    assert outputs_match("hai\nmot\n", "mot\nhai\n") is False


def test_a_truncated_output_never_matches():
    """Past the cap we do not have the output, only its beginning.

    A program can print a megabyte of the expected answer and then keep going;
    the kept part would compare equal while the real output is nothing of the
    sort. The cap is what stops a submission from deciding how much memory the
    worker uses, and this is the price of it -- one that only a submission
    printing more than a megabyte ever pays.
    """
    assert outputs_match("42\n", "42\n", truncated=True) is False


@pytest.mark.parametrize("oddity", ["\x0b", "\x0c", "\x85", " "])
def test_exotic_control_characters_are_not_treated_as_line_breaks(oddity):
    """Python's `splitlines` breaks on eleven characters, not one.

    Comparing with it would make "a\\x0bb" and "a\\nb" the same answer, so the
    normaliser splits on the newline it was told about and nothing else.
    """
    assert outputs_match(f"a{oddity}b\n", "a\nb\n") is False


def test_normalising_is_idempotent():
    """Normalising twice changes nothing the first pass left.

    Worth pinning: the verdict layer above is free to store the normalised
    output and compare it again later without the answer drifting.
    """
    once = normalize("  a \r\n\r\nb\t\n\n\n")
    assert normalize(once) == once


def test_what_normalising_leaves_behind():
    """The rules above, read as one string rather than as a dozen matches."""
    assert normalize("  a \r\n\r\nb\t\n\n\n") == "  a\n\nb"
