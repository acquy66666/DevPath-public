"""Decide whether what a program printed is the answer that was expected.

This is the whole of the platform's "right answer" policy, and it is
deliberately a page of pure functions: no container, no submission, no Docker.
The sandbox next door answers what a program did; this answers whether it was
correct, and the two are tested apart because they fail for entirely different
reasons.

The policy in one line: forgive what a text editor did, judge what the program
decided. Line endings, trailing spaces on a line, and blank lines at the end of
the output are the editor's; everything else -- indentation, spacing inside a
line, blank lines between lines, order, case -- is the program's.
"""

from __future__ import annotations

# Stripped from the end of every line. Space and tab are what a stray `print`
# argument or a loop that appends a separator leaves behind; the vertical tab
# and form feed are here because no exercise means to end a line with one.
# Deliberately not `str.rstrip()` with no argument, which also strips
# non-breaking space and a handful of Unicode separators -- characters a
# program prints on purpose, or not at all.
TRAILING_WHITESPACE = " \t\v\f"


def normalize(text: str) -> str:
    """Put output in the form both sides are compared in.

    Applied to the expected output as much as to the actual one: an instructor
    pasting expected output from a Windows editor must not be the reason a
    correct submission fails.
    """
    # Split on the newline we were told about and nothing else. `splitlines`
    # would break on eleven different characters, so a program printing a form
    # feed would be read as having printed a new line and could pass a test it
    # did not answer.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip(TRAILING_WHITESPACE) for line in lines]

    # Whether the output ends with a newline, with three of them, or with none
    # is not something an exercise asks about -- and `print` versus
    # `sys.stdout.write` decides it for the student either way.
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


def outputs_match(actual: str, expected: str, *, truncated: bool = False) -> bool:
    """Whether `actual` is the expected answer, once both are normalised.

    `truncated` says the runner stopped keeping output at its cap, and it
    settles the question on its own: what came back is a prefix, and a prefix
    that happens to equal the expected answer tells us nothing about the
    megabytes that followed it. Calling that a match would let a program pass
    by printing the answer and then shouting.
    """
    if truncated:
        return False

    return normalize(actual) == normalize(expected)
