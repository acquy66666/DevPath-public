"""The runner core: one file, one stdin, one container, every limit applied.

What is under test is a small promise with a lot behind it -- give this a
program and some input, and get back what it printed, how it ended, and how
long it took, without the program being able to affect anything else on the
machine and without it being able to run forever.

Turning that into a verdict is the next task. Here the only questions are
whether the program ran, whether the limits were really there, and whether the
runner cleans up after itself.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from runner.images import PYTHON_IMAGE
from runner.sandbox import (
    GRADING_LABEL,
    WORKSPACE_ROOT_ENV,
    Limits,
    Outcome,
    execute,
    workspace_root,
)

# Every test in this module starts a container, so the images have to exist
# and Docker has to be running.
pytestmark = pytest.mark.usefixtures("sandbox_images")

FIXTURES = Path(__file__).parent / "fixtures"


def submission(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# Short limits, so the tests that have to wait for a timeout wait seconds
# rather than a quarter of a minute. The relationship between the two layers
# is what is being tested, not the size of the numbers.
QUICK = Limits(cpu_seconds=1, startup_grace_seconds=2.0)


def test_it_runs_a_program_and_brings_back_what_it_printed():
    result = execute(submission("hello.py"))

    assert result.outcome is Outcome.EXITED
    assert result.exit_code == 0
    assert result.stdout == "Xin chao\n"
    assert result.stderr == ""


def test_stdin_reaches_the_program():
    result = execute(submission("echo_stdin.py"), stdin="mot\nhai\n")

    assert result.outcome is Outcome.EXITED
    assert result.stdout == "MOT\nHAI\n"


def test_a_program_that_raises_comes_back_with_its_traceback_and_exit_code():
    """Both streams are kept apart.

    The traceback is what the student needs to see; the printed line is what
    the answer would have been compared against. Merging them would put a
    Python traceback into the output being graded.
    """
    result = execute(submission("crash.py"))

    assert result.outcome is Outcome.EXITED
    assert result.exit_code == 1
    assert result.stdout == "truoc khi loi\n"
    assert "ValueError: khong chia duoc cho 0" in result.stderr


def test_a_busy_loop_is_stopped_by_the_cpu_limit_inside_the_container():
    """The first of the two timeout layers, and the one that does the work.

    RLIMIT_CPU counts CPU seconds, so it is unaffected by how busy the host
    is: the same infinite loop is stopped after the same amount of computing
    whether the machine is idle or grading ten submissions at once.
    """
    result = execute(submission("burn_cpu.py"), limits=QUICK)

    assert result.outcome is Outcome.CPU_TIME_EXCEEDED
    # 128 + SIGXCPU: the *soft* limit, which lands exactly on the budget. The
    # hard limit a second later would be 137, and seeing that here would mean
    # the soft signal had been swallowed -- see the PID 1 test below.
    assert result.exit_code == 152
    assert result.duration_seconds < QUICK.wall_seconds


def test_a_sleeping_program_is_stopped_by_the_wall_clock_outside_it():
    """The second layer, for everything the first one cannot see.

    A program asleep, or blocked reading input that will never come, uses no
    CPU at all and would sit in the queue forever. Only a clock outside the
    container ends that, which is why one layer is not enough.
    """
    result = execute(submission("sleep_forever.py"), limits=QUICK)

    assert result.outcome is Outcome.WALL_TIME_EXCEEDED
    assert result.duration_seconds >= QUICK.wall_seconds


def test_what_a_killed_program_had_already_printed_still_comes_back():
    """Being killed is not the same as having printed nothing.

    The student should see the line their program reached before the limit
    stopped it -- often it is the whole explanation of why it was too slow.
    """
    result = execute(submission("sleep_forever.py"), limits=QUICK)

    assert result.stdout == "dang cho\n"


def test_a_program_that_asks_for_too_much_memory_is_killed_by_the_kernel():
    result = execute(submission("eat_memory.py"), limits=QUICK)

    assert result.outcome is Outcome.OUT_OF_MEMORY


def test_a_flood_of_output_is_cut_at_the_limit():
    """The output is read with a cap, not read and then trimmed.

    A program printing in a loop can produce hundreds of megabytes in the
    seconds it is given. Reading all of it to throw most of it away would let
    one submission decide how much memory the worker uses.
    """
    limits = Limits(cpu_seconds=1, output_bytes=50_000)
    result = execute(submission("flood_output.py"), limits=limits)

    assert result.stdout_truncated is True
    assert len(result.stdout.encode()) <= 50_000


def test_every_limit_the_runner_promises_is_present_inside_the_container():
    """One program, run as a submission, reporting on its own cell.

    This is the test that would notice a flag quietly dropped from the docker
    command line -- the place a sandbox usually fails, since nothing else
    about grading would look any different.
    """
    limits = Limits(cpu_seconds=2, memory_mb=128, pids=32, cpus=0.5)
    result = execute(submission("report_limits.py"), limits=limits)

    assert result.outcome is Outcome.EXITED, result.stderr
    seen = json.loads(result.stdout)

    assert seen["uid"] == 10001 and seen["gid"] == 10001
    # Soft limit first, so the program gets SIGXCPU and dies; the hard limit a
    # second later is for a program that installs a handler and ignores it.
    assert seen["rlimit_cpu"] == [2, 3]
    assert seen["memory_max"] == str(128 * 1024 * 1024)
    # Swap set equal to memory means "no swap": a program cannot buy itself
    # more room by pushing pages to disk, which would turn a memory limit into
    # a very slow program instead of a stopped one.
    assert seen["memory_swap_max"] == "0"
    assert seen["pids_max"] == "32"
    assert seen["cpu_max"] == "50000 100000"
    assert seen["interfaces"] == ["lo"]
    assert seen["capabilities"] == "0000000000000000"
    assert seen["no_new_privs"] == "1"
    assert seen["rootfs_write"] == "Read-only_file_system"
    assert seen["tmp_write"] == "wrote"


def test_the_submission_does_not_run_as_pid_1():
    """The discovery that made the inner timeout work at all.

    The kernel does not apply default signal actions to PID 1: a signal with
    no handler installed is discarded rather than killing it. Run the
    submission as PID 1 and SIGXCPU vanishes, the soft CPU limit does nothing,
    and every program that runs too long is killed a second late by SIGKILL --
    with an exit code indistinguishable from a crash. Measured on this
    machine: exit 137 after 2.4s without an init process, exit 152 after 1.5s
    with one, for the same one-second budget.

    Nothing about grading looks wrong when this regresses, which is why it is
    worth a test of its own.
    """
    seen = json.loads(execute(submission("report_limits.py")).stdout)

    assert seen["pid"] != 1


def test_the_submission_sees_its_own_file_and_nothing_else_of_the_runners():
    """The mounted directory holds exactly one file.

    The runner's own scratch files -- the input it feeds in, anything it
    writes down -- live outside the mount. Putting them next to the source
    would hand the submission both the test input and a way to import
    whatever it found there.
    """
    result = execute(submission("report_limits.py"))

    assert json.loads(result.stdout)["sandbox_dir"] == ["main.py"]


def test_no_container_is_left_behind():
    """A worker grades thousands of submissions and must leak none of them.

    Including the ones it had to kill: a container stopped by the wall clock
    is exactly the one most likely to be forgotten.
    """
    execute(submission("sleep_forever.py"), limits=QUICK)

    left = subprocess.run(
        ["docker", "ps", "--all", "--quiet", "--filter", f"label={GRADING_LABEL}"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert left.stdout.strip() == ""


def test_a_missing_image_is_the_systems_fault_not_the_students():
    """SE exists so that our failures are never charged to a submission.

    A daemon that is down, an image that was never built: the student's code
    was not even reached, and telling them their answer was wrong would be a
    lie.
    """
    result = execute(submission("hello.py"), image="devpath-sandbox-does-not-exist:v0")

    assert result.outcome is Outcome.SYSTEM_ERROR
    assert result.exit_code is None
    assert "devpath-sandbox-does-not-exist" in result.system_error


def test_the_image_it_grades_with_is_the_one_the_platform_ships():
    """A guard against the default drifting away from the built image."""
    assert execute(submission("hello.py")).image == PYTHON_IMAGE


@pytest.mark.parametrize(
    ("cpu_seconds", "cpus", "expected"),
    [(5, 0.5, 15.0), (5, 1.0, 9.0), (2, 0.25, 15.0)],
)
def test_the_wall_clock_is_derived_from_the_cpu_budget_not_guessed(cpu_seconds, cpus, expected):
    """The trap this arithmetic exists to avoid.

    A container given half a core needs two seconds of wall time per second of
    CPU. Pick the wall timeout independently -- five seconds for a five second
    CPU budget, say -- and the outer layer always fires first, the CPU limit
    never applies, and grading silently starts depending on how busy the host
    is. Deriving one from the other keeps both layers alive, and the extra CPU
    second in the numerator is the kernel's own grace between SIGXCPU and
    SIGKILL.
    """
    assert Limits(cpu_seconds=cpu_seconds, cpus=cpus).wall_seconds == expected


def test_the_workspace_root_defaults_to_the_system_temp_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset is the right answer on a developer machine and in CI.

    It matters only where the runner is itself inside a container: the daemon
    resolves the sandbox's bind mount on the host, so the directory holding a
    submission has to exist on both sides under the same name. The worker sets
    this; nothing else does.
    """
    monkeypatch.delenv(WORKSPACE_ROOT_ENV, raising=False)
    assert workspace_root() is None

    monkeypatch.setenv(WORKSPACE_ROOT_ENV, "/var/lib/devpath-grading")
    assert workspace_root() == "/var/lib/devpath-grading"


def test_a_submission_is_written_where_the_workspace_root_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And the directory is gone again afterwards, wherever it was."""
    root = tmp_path / "workspaces"
    root.mkdir()
    monkeypatch.setenv(WORKSPACE_ROOT_ENV, str(root))

    execution = execute("print('xin chào')")

    assert execution.stdout.strip() == "xin chào"
    assert list(root.iterdir()) == []
