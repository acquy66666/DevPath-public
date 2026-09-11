"""Run one submitted program, once, inside one disposable container.

This is the core the whole grading pipeline sits on: give it a source file and
some standard input, get back what the program printed, how it ended, and how
long it took. It decides nothing about right or wrong -- comparing output and
naming a verdict come after, and keeping that line clear is what lets the
verdict rules be tested without a container and the container be tested
without any notion of a correct answer.

Two rules shape everything here:

  * the submission is hostile until proven otherwise. It arrives as a file on
    a read-only mount and as argv, never as part of a shell command, and it is
    never trusted to end on its own.
  * our failures are never charged to the student. A daemon that is down or an
    image that was never built is SYSTEM_ERROR, which the caller must not turn
    into "wrong answer".
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from runner.images import PYTHON_IMAGE, SANDBOX_UID

# Every container this module starts carries it, so a crashed worker's
# leftovers can be found and reaped by one command that cannot possibly match
# anything else on the host.
GRADING_LABEL = "devpath.grading=1"

# What the kernel adds between the soft CPU limit and the hard one: SIGXCPU
# first, then a second of grace, then SIGKILL.
HARD_LIMIT_MARGIN_SECONDS = 1

SOURCE_FILENAME = "main.py"
MOUNT_POINT = "/sandbox"

# Where the per-run workspace is created. Unset means the system temp
# directory, which is right everywhere except inside a container.
#
# The path in `--mount source=` is resolved by the daemon, on the host. A
# runner running *in* a container therefore asks for a directory that only
# exists inside itself, and Docker answers "bind source path does not exist"
# -- our own failure, reported as SYSTEM_ERROR, on every single submission.
# The fix is a directory both sides can see under the same name: the worker
# bind-mounts one host path onto the identical path inside itself and points
# this at it. Nothing else changes, and on a developer machine running the
# tests directly this stays unset.
WORKSPACE_ROOT_ENV = "DEVPATH_GRADING_WORKSPACE"


def workspace_root() -> str | None:
    """Read per call, not at import: a worker sets it, the tests do not."""
    return os.environ.get(WORKSPACE_ROOT_ENV) or None

# The program travels as argv, never as a shell command line, so there is
# nothing for a filename or a piece of code to break out of.
#
# By its bare name, from a working directory set to the mount: a traceback
# names the file it was raised in, and "File "main.py", line 2" is a sentence
# about the student's own file, while "File "/sandbox/main.py"" is a sentence
# about our container. Same file, same line, one of them readable by the
# person who has to fix it.
RUN_COMMAND = ("python3", SOURCE_FILENAME)

# Compiles the submission without running a line of it, and says why if it
# cannot. Python has no compile step of its own, which is exactly why this
# exists: without it a syntax error would arrive as a runtime error on every
# test case, each one paying for a container, and the student would be told
# their program failed a case it never reached.
#
# Read as bytes and handed to `compile` whole, because that is what the
# interpreter does -- it is what makes an encoding declaration, a BOM, or a
# broken one behave here exactly as it would locally. The file is named
# `main.py` in the message rather than by its path inside the container:
# students should read a message about their file, not about our mount. And
# only the exception is printed, not the traceback, so the checker's own frame
# never appears in it.
_COMPILE_CHECKER = """\
import sys, traceback
try:
    with open(sys.argv[1], "rb") as source:
        compile(source.read(), "main.py", "exec")
except (SyntaxError, ValueError) as exc:
    sys.stderr.write("".join(traceback.format_exception_only(type(exc), exc)))
    raise SystemExit(1)
"""
COMPILE_COMMAND = ("python3", "-c", _COMPILE_CHECKER, SOURCE_FILENAME)

# 128 + SIGXCPU(24): the CPU limit's soft signal, whose default action is to
# terminate the process -- provided the process is not PID 1. See `--init`.
SIGXCPU_EXIT = 152
# 128 + SIGKILL(9). The CPU limit's hard stop, one second of CPU after the soft
# one, for a program that installed a handler and refused to die.
SIGKILL_EXIT = 137


class Outcome(StrEnum):
    """How the run ended -- a fact about the process, not a judgement.

    EXITED covers every program that reached its own end, whether it printed
    the right answer, the wrong one, or a traceback.
    """

    EXITED = "exited"
    CPU_TIME_EXCEEDED = "cpu_time_exceeded"
    WALL_TIME_EXCEEDED = "wall_time_exceeded"
    OUT_OF_MEMORY = "out_of_memory"
    SYSTEM_ERROR = "system_error"


@dataclass(frozen=True)
class Limits:
    """The cell a submission runs in.

    Instructors get to set `cpu_seconds` per exercise, within a ceiling. The
    rest are platform-wide and deliberately not per-exercise: they are what
    keeps one submission from affecting the next one, and that is not a
    teaching decision.
    """

    cpu_seconds: int = 5
    cpus: float = 0.5
    memory_mb: int = 256
    pids: int = 64
    tmpfs_mb: int = 64
    output_bytes: int = 1_000_000
    # Container startup, interpreter startup, and reading the input: time the
    # program is alive but has not begun computing.
    startup_grace_seconds: float = 3.0

    @property
    def wall_seconds(self) -> float:
        """The outer timeout, derived rather than chosen.

        A container given half a core needs two seconds of wall time for every
        second of CPU it is allowed. Pick this number independently -- five
        seconds of wall for five seconds of CPU, the obvious guess -- and the
        outer layer fires first every time, the CPU limit never applies at
        all, and how long a submission may run quietly becomes a function of
        how busy the host is. Deriving it keeps both layers doing their own
        job.

        The hard-limit margin is in here for the same reason: a program that
        catches SIGXCPU gets one more CPU second before the kernel kills it,
        and the wall clock must not go off during that second or it would take
        the credit for a stop the inner layer had already arranged.
        """
        return (self.cpu_seconds + HARD_LIMIT_MARGIN_SECONDS) / self.cpus + (
            self.startup_grace_seconds
        )


DEFAULT_LIMITS = Limits()


@dataclass(frozen=True)
class Execution:
    outcome: Outcome
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    duration_seconds: float
    image: str
    #: Filled in only for SYSTEM_ERROR: what went wrong on our side.
    system_error: str = ""


def execute(
    source: str,
    *,
    stdin: str = "",
    limits: Limits = DEFAULT_LIMITS,
    image: str = PYTHON_IMAGE,
    command: Sequence[str] = RUN_COMMAND,
) -> Execution:
    """Run `source` against `stdin` in a fresh container and clean up after it.

    `command` is what the container is told to do with the file; it is ours,
    never the submission's. The compile check is the same cell with the same
    limits and a different verb, which is the point -- checking a hostile
    file's syntax is still running a parser over a hostile file.
    """
    workspace = Path(tempfile.mkdtemp(prefix="devpath-grading-", dir=workspace_root()))
    container = f"devpath-grading-{uuid.uuid4().hex}"

    try:
        # Two directories, and only one of them is mounted. The runner's own
        # scratch files sit outside, because anything beside the source is
        # something the submission can read -- including the test input it is
        # supposed to be solving blind -- or import.
        code_dir = workspace / "code"
        code_dir.mkdir()
        source_file = code_dir / SOURCE_FILENAME
        # Bytes, not text. On Windows `write_text` turns every newline into
        # a carriage return plus a newline, which would rewrite the student's
        # source on the way in and -- far worse -- put a carriage return on
        # the end of every line of test input, so a correct program would be
        # marked wrong over a character nobody can see. What was submitted is
        # what runs.
        source_file.write_bytes(source.encode("utf-8"))
        # World-readable: the file is written by the worker's user and read by
        # an unrelated uid inside the container.
        source_file.chmod(0o644)

        stdin_file = workspace / "stdin"
        stdin_file.write_bytes(stdin.encode("utf-8"))

        created = _docker(
            "create",
            *_container_flags(container, code_dir, limits),
            image,
            *command,
        )
        if created.returncode != 0:
            return _system_error(created.stderr or created.stdout, image)

        return _start_and_wait(container, stdin_file, limits, image)
    finally:
        # Force, because the container may still be running, and unconditional
        # because a worker that leaks one container per killed submission runs
        # a host out of disk in a day.
        _docker("rm", "--force", container)
        shutil.rmtree(workspace, ignore_errors=True)


def _container_flags(container: str, code_dir: Path, limits: Limits) -> list[str]:
    """The security invariants, in the one place they can be read as a list.

    Each of these is load-bearing; the test that reads them back from inside a
    running container is what proves none of them has quietly gone missing.
    """
    return [
        "--name", container,
        "--label", GRADING_LABEL,
        "--interactive",
        # Not a nicety. Without it the submission is PID 1, and the kernel does
        # not apply default signal actions to PID 1 -- SIGXCPU arrives, has no
        # handler, and is discarded, so the soft CPU limit does nothing and the
        # program runs on until the hard limit kills it a second later.
        # Measured: 137 after 2.4s without, 152 after 1.5s with, for a one
        # second CPU budget. With an init process in front, the submission is
        # an ordinary child, the soft limit lands on time, and the exit code
        # says which limit ended it.
        "--init",
        # Never reach for the network mid-grading, not even to fetch the image
        # this is supposed to have built already. A missing image is a
        # deployment mistake and should say so immediately.
        "--pull", "never",
        "--network", "none",
        "--read-only",
        f"--tmpfs=/tmp:rw,nosuid,nodev,noexec,size={limits.tmpfs_mb}m",
        "--memory", f"{limits.memory_mb}m",
        # Equal to memory, which means no swap at all: otherwise a program over
        # its limit would be pushed to disk and become slow instead of stopped,
        # and the memory limit would show up as a mysterious timeout.
        "--memory-swap", f"{limits.memory_mb}m",
        "--cpus", str(limits.cpus),
        "--pids-limit", str(limits.pids),
        # The inner half of the two-layer timeout. Soft first so the program
        # gets SIGXCPU and dies; the hard limit a second later is for one that
        # catches the signal and carries on.
        "--ulimit", f"cpu={limits.cpu_seconds}:{limits.cpu_seconds + 1}",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        # The image already says this. Saying it twice costs nothing and means
        # neither half has to be the only one that is right.
        "--user", f"{SANDBOX_UID}:{SANDBOX_UID}",
        # Output is already being read off the attached stream; letting the
        # daemon keep a second copy would let a program printing in a loop fill
        # the host's disk with a log nobody will ever read.
        "--log-driver", "none",
        "--mount", f"type=bind,source={code_dir},target={MOUNT_POINT},readonly",
        # So the submission is named by the name the student gave it, in
        # tracebacks and in the compile message alike. Read-only, like the
        # mount it is: a working directory is not somewhere to write.
        "--workdir", MOUNT_POINT,
    ]


def _start_and_wait(container: str, stdin_file: Path, limits: Limits, image: str) -> Execution:
    with stdin_file.open("rb") as feed:
        started = time.monotonic()
        process = subprocess.Popen(
            ["docker", "start", "--attach", "--interactive", container],
            stdin=feed,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out = _CappedReader(process.stdout, limits.output_bytes)
        err = _CappedReader(process.stderr, limits.output_bytes)

        hit_the_wall = False
        try:
            process.wait(timeout=limits.wall_seconds)
        except subprocess.TimeoutExpired:
            # The outer layer. Killing the docker client would leave the
            # container running -- the process to stop is on the other side of
            # the daemon, not this one.
            hit_the_wall = True
            _docker("kill", container)
            process.wait(timeout=30)

        duration = time.monotonic() - started

    out.join(timeout=10)
    err.join(timeout=10)

    state = _inspect(container)
    if state is None:
        return _system_error(f"container {container} vanished before it could be inspected", image)

    exit_code, oom_killed = state
    return Execution(
        outcome=_classify(exit_code, oom_killed, hit_the_wall),
        exit_code=exit_code,
        stdout=out.text,
        stderr=err.text,
        stdout_truncated=out.truncated,
        stderr_truncated=err.truncated,
        duration_seconds=duration,
        image=image,
    )


def _classify(exit_code: int, oom_killed: bool, hit_the_wall: bool) -> Outcome:
    """Name the way the run ended, most specific cause first.

    A container over its memory limit also exits 137, so the kernel's own
    verdict has to be read before the exit code is interpreted.
    """
    if oom_killed:
        return Outcome.OUT_OF_MEMORY
    if hit_the_wall:
        return Outcome.WALL_TIME_EXCEEDED
    if exit_code in (SIGXCPU_EXIT, SIGKILL_EXIT):
        # 152 is the ordinary path: the soft limit, on time. 137 is the hard
        # limit that follows it for a program that caught the signal and kept
        # going. A program that sends itself SIGKILL also lands here and is
        # charged a time limit rather than a runtime error -- a misreading, but
        # of a submission that was failing either way.
        return Outcome.CPU_TIME_EXCEEDED
    return Outcome.EXITED


class _CappedReader(threading.Thread):
    """Drains a stream, keeping at most `cap` bytes of it.

    Two things have to be true at once. The worker must never hold more than
    the cap in memory, because how much a submission prints is the
    submission's decision. And the stream must keep being read even after the
    cap: a program blocked on a full pipe stops using CPU, so its own limits
    stop applying and only the wall clock is left to end it.
    """

    def __init__(self, stream, cap: int) -> None:
        super().__init__(daemon=True)
        self._stream = stream
        self._cap = cap
        self._kept = bytearray()
        self.truncated = False
        self.start()

    def run(self) -> None:
        while chunk := self._stream.read(65536):
            room = self._cap - len(self._kept)
            if room > 0:
                self._kept += chunk[:room]
            if len(chunk) > room:
                self.truncated = True

    @property
    def text(self) -> str:
        # A submission is free to write bytes that are not text at all, and
        # that is not a reason to lose the rest of its output. The image forces
        # UTF-8, so anything unreadable here was written deliberately.
        return bytes(self._kept).decode("utf-8", errors="replace")


def _inspect(container: str) -> tuple[int, bool] | None:
    finished = _docker(
        "inspect", "--format", "{{.State.ExitCode}} {{.State.OOMKilled}}", container
    )
    if finished.returncode != 0:
        return None

    exit_code, oom_killed = finished.stdout.split()
    return int(exit_code), oom_killed == "true"


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _system_error(message: str, image: str) -> Execution:
    return Execution(
        outcome=Outcome.SYSTEM_ERROR,
        exit_code=None,
        stdout="",
        stderr="",
        stdout_truncated=False,
        stderr_truncated=False,
        duration_seconds=0.0,
        image=image,
        system_error=message.strip(),
    )
