"""What has to be true of the Python sandbox image before any code runs in it.

These tests are about the *image*: who it runs as, what is installed in it,
what a program inside it is allowed to touch. The attacks themselves -- the
network, the fork bomb, reading outside the mount -- are the next task and get
their own suite. The only runtime flags used here are the ones needed to state
a claim about the image itself.

Every assertion is made from inside a running container, because that is the
only place the answer counts. `docker inspect` would report what the image
*says*; running a program reports what the kernel actually allows.
"""

from __future__ import annotations

import subprocess
import textwrap

from runner.images import PYTHON_IMAGE

# The flags the grading worker will put on every submission, from the security
# invariants in the `sandbox-grading` skill. Deliberately no `--user`: the
# worker will pass that too, but the image has to be safe without it -- see
# test_it_does_not_run_as_root_even_if_the_runner_forgets_to_say_so.
HARDENING = [
    "--network", "none",
    "--read-only",
    "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
    "--memory", "256m",
    "--memory-swap", "256m",
    "--cpus", "0.5",
    "--pids-limit", "64",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
]


def run(
    code: str,
    *,
    flags: list[str] | None = None,
    stdin: str = "",
) -> subprocess.CompletedProcess[str]:
    """Run a snippet in the sandbox and hand back the finished process.

    The program travels through argv, never through a shell -- the same rule
    the runner follows for a submitted file, and the reason a snippet
    containing a quote cannot turn into a command here.

    `encoding` is explicit because the dev machine's console codepage is not
    UTF-8, and letting Python guess it would mangle any non-ASCII output on
    the way back in.
    """
    return subprocess.run(
        [
            "docker", "run", "--rm", "--interactive",
            *(HARDENING if flags is None else flags),
            PYTHON_IMAGE,
            "python3", "-c", textwrap.dedent(code),
        ],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def test_it_runs_the_python_version_the_platform_targets():
    result = run("import sys; print('%d.%d' % sys.version_info[:2])")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "3.12"


def test_it_does_not_run_as_root_even_if_the_runner_forgets_to_say_so():
    """`--user` is one typo away from absent; USER inside the image is not.

    The uid is part of the contract rather than an accident: the worker names
    the same number when it decides who owns the files it mounts in.
    """
    result = run("import os; print(os.getuid(), os.getgid())")

    assert result.stdout.strip() == "10001 10001"


def test_the_root_filesystem_is_read_only():
    result = run(
        """
        import errno
        try:
            open('/usr/local/lib/python3.12/evil.py', 'w')
        except OSError as error:
            print(errno.errorcode[error.errno])
        """
    )

    assert result.stdout.strip() == "EROFS"


def test_the_system_directories_resist_writes_even_without_the_read_only_flag():
    """Two locks on the same door.

    `--read-only` is a flag the worker passes; file ownership is a property of
    the image. If the flag ever goes missing, an unprivileged uid still cannot
    write into a root-owned directory, and the failure mode stays "this
    submission crashes" rather than "the image is now something else".
    """
    result = run(
        """
        import errno
        try:
            open('/usr/local/lib/python3.12/evil.py', 'w')
        except OSError as error:
            print(errno.errorcode[error.errno])
        """,
        flags=[flag for flag in HARDENING if flag != "--read-only"],
    )

    assert result.stdout.strip() == "EACCES"


def test_tmp_is_the_one_place_a_program_may_write():
    """Some correct solutions need scratch space; they get exactly this much.

    It is a tmpfs the worker sizes, so it dies with the container and can never
    be the channel by which one submission leaves something for the next.
    """
    result = run(
        """
        with open('/tmp/scratch.txt', 'w') as handle:
            handle.write('ok')
        print(open('/tmp/scratch.txt').read())
        """
    )

    assert result.stdout.strip() == "ok"


def test_the_directory_the_submission_is_mounted_into_belongs_to_root():
    """The program runs in /sandbox and cannot add a file next to itself.

    Mode 555 and root ownership, so this holds even before the mount is made
    read-only -- a submission cannot drop a `sitecustomize.py` beside its own
    source and have the next process import it.
    """
    result = run(
        """
        import os
        info = os.stat('/sandbox')
        print(os.getcwd(), info.st_uid, oct(info.st_mode & 0o777))
        """
    )

    assert result.stdout.split() == ["/sandbox", "0", "0o555"]


def test_there_is_no_way_to_install_anything():
    result = run(
        """
        import importlib.util
        import shutil
        print(shutil.which('pip'), shutil.which('pip3'))
        print(importlib.util.find_spec('pip'), importlib.util.find_spec('ensurepip'))
        """
    )

    assert result.stdout.split() == ["None"] * 4


def test_only_the_standard_library_is_importable():
    """No third-party distribution in the image, now or by accident later.

    This is what keeps grading reproducible: a solution that passes today
    cannot start failing tomorrow because a package drifted a version, and a
    submission cannot depend on something the exercise never promised it.
    """
    result = run(
        """
        from importlib.metadata import distributions
        print(sorted(dist.metadata['Name'] for dist in distributions()))
        """
    )

    assert result.stdout.strip() == "[]"


SETUID_SCAN = """
import os
import stat

found = []
for root, dirs, files in os.walk('/', onerror=lambda error: None):
    if root in ('/proc', '/sys', '/dev'):
        dirs[:] = []
        continue
    for name in files:
        path = os.path.join(root, name)
        try:
            mode = os.lstat(path).st_mode
        except OSError:
            continue
        if stat.S_ISREG(mode) and mode & (stat.S_ISUID | stat.S_ISGID):
            found.append(path)

print(sorted(found))
"""


def test_no_setuid_binary_survives_in_the_image():
    """A third lock, for the day one of the first two is missing.

    `--cap-drop ALL` and `no-new-privileges` already make a setuid binary
    useless, but both of those are flags on a command line. Stripping the bits
    is a property of the image, and this is the test that notices when a future
    base image brings a fresh `su` back in.
    """
    result = run(SETUID_SCAN)

    assert result.stdout.strip() == "[]"


def test_text_is_utf8_so_vietnamese_output_survives_the_round_trip():
    """The courses are in Vietnamese; so will be the expected output.

    Under a C locale Python would answer in ASCII and every accented character
    would come back mangled -- and the student would be told their correct
    answer was wrong.
    """
    result = run(
        """
        import sys
        print(sys.stdout.encoding)
        print('Xin ch\\u00e0o, \\u0111\\u00e2y l\\u00e0 b\\u00e0i n\\u1ed9p')
        """
    )

    lines = result.stdout.splitlines()
    assert lines[0].lower() == "utf-8"
    assert lines[1] == "Xin chào, đây là bài nộp"


def test_output_written_before_a_crash_still_reaches_the_grader():
    """`os._exit` skips every buffer flush, which is what makes this a test.

    A program killed for exceeding its time limit dies the same way. With a
    block-buffered stdout the partial output would vanish, and the student
    would be shown an empty run instead of the line their program reached.
    """
    result = run(
        """
        import os
        print('printed before the crash')
        os._exit(1)
        """
    )

    assert result.returncode == 1
    assert result.stdout.strip() == "printed before the crash"


def test_the_same_submission_behaves_the_same_way_on_every_run():
    """A fixed hash seed, so a verdict is a property of the code.

    Python randomises string hashing per process by default, which makes the
    iteration order of a set differ between runs. A submission that printed a
    set would then be AC once and WA the next time on identical code -- graded
    by whichever run the queue happened to hand it.
    """
    outputs = {run("print(hash('devpath'))").stdout.strip() for _ in range(2)}

    assert len(outputs) == 1
