"""The attacks, run for real, and stopped for real.

This is the suite the whole sandbox exists for, and it is written the way the
`sandbox-grading` skill demands: every invariant has a program in
`tests/fixtures/` that tries to break it, and the assertion is made from
inside the container by the attacker itself. `docker inspect` would tell us
what we asked for. These files tell us what the kernel actually allowed.

Each fixture reports one line per attempt, beginning with BLOCKED or ESCAPED,
and the first assertion of every test is the same: the word ESCAPED does not
appear. The rest of each test pins down *how* the attempt failed, because "it
did not work" is a weaker claim than "the kernel refused it with EPERM" -- the
first can be true by accident, on one machine, on one day.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runner.sandbox import Limits, Outcome, execute

pytestmark = pytest.mark.usefixtures("sandbox_images")

FIXTURES = Path(__file__).parent / "fixtures"

# Enough CPU for a program that walks /proc or writes 64 MB, short enough that
# a failure to block something does not cost a minute of waiting.
ATTACK_LIMITS = Limits(cpu_seconds=5, startup_grace_seconds=3.0)


def attack(name: str) -> tuple[str, str]:
    """Run one attack and hand back what it managed to report."""
    result = execute((FIXTURES / name).read_text(encoding="utf-8"), limits=ATTACK_LIMITS)
    assert result.outcome is not Outcome.SYSTEM_ERROR, result.system_error
    # Nothing here should crash: an attack that dies of an unhandled exception
    # proves nothing about the wall it was thrown at.
    assert "Traceback" not in result.stderr, result.stderr
    return result.stdout, result.stderr


def test_the_network_is_not_there_at_all():
    """Every route out, refused before it leaves the process.

    ENETUNREACH rather than a timeout is the detail worth having: the kernel
    has no route to give, which is what `--network none` means. A timeout
    would suggest a firewall somewhere, and firewalls can be misconfigured.
    """
    report, _ = attack("attack_network.py")

    assert "ESCAPED" not in report
    assert report.count("BLOCKED") == 6
    assert "ENETUNREACH" in report
    # Loopback and nothing else. An interface list with `eth0` in it would
    # mean the container was on a bridge and only routing had been removed.
    assert "interfaces visible: ['lo']" in report


def test_nothing_outside_the_mount_can_be_read():
    """The daemon's socket above all.

    A submission that reaches `/var/run/docker.sock` does not need to escape
    the sandbox -- it can ask the daemon for a container without one.
    """
    report, _ = attack("attack_read_outside_mount.py")

    assert "ESCAPED" not in report
    assert "/var/run/docker.sock       does not exist" in report
    # Not root: the file is there, and reading it is still refused.
    assert "/etc/shadow                PermissionError" in report
    # A third layer, neither the image's nor the runner's: the daemon replaces
    # the dangerous entries in /proc with a bind mount of /dev/null.
    #
    # The report travels with the failure on purpose. This assertion is about
    # what the host's daemon does, so when it breaks it breaks on someone
    # else's machine, and pytest's own truncation cuts out the one line that
    # would say what happened instead.
    assert "MASKED   /proc/kcore" in report, report
    # Where a careless bind mount would have landed, and nothing is there.
    assert "/media                     an empty directory: []" in report
    # One file in the mount, the one the student submitted. The test input
    # they are meant to solve blind is written outside it.
    assert "contents of the mount: ['main.py']" in report
    # The worker's environment is where the database URL and the API keys
    # live, and none of it travels into the cell. A new name appearing here is
    # worth a red build even when it turns out to be harmless.
    assert "environment variables that are not image furniture: []" in report


def test_a_submission_can_only_throw_its_own_run_away():
    """The limitation, stated rather than hidden.

    `docker-init` handles SIGTERM, and handling it means shutting down, so a
    submission can end its own container. It cannot reach any other: signals
    do not cross a PID namespace. The run comes back non-zero, which is a
    runtime error, and nothing else on the machine noticed.
    """
    result = execute(
        (FIXTURES / "attack_kill_own_container.py").read_text(encoding="utf-8"),
        limits=ATTACK_LIMITS,
    )

    assert "ESCAPED" not in result.stdout
    assert result.outcome is Outcome.EXITED
    # 128 + SIGTERM(15). Not zero, so the submission is charged a runtime
    # error rather than being accepted for printing nothing.
    assert result.exit_code == 143


def test_the_filesystem_cannot_be_changed_except_for_tmp():
    """What a submission writes must not outlive it, or reach the next one.

    Poisoning the standard library is the attack that matters: one write into
    `os.py` and every submission that follows imports the attacker's code.
    """
    report, _ = attack("attack_write_rootfs.py")

    assert "ESCAPED" not in report
    assert "BROKEN" not in report
    assert report.count("BLOCKED") == 7
    assert "Read-only file system" in report
    # The exception, and it has to keep working.
    assert "ALLOWED" in report


def test_a_fork_bomb_stops_at_the_pid_limit():
    """The denial of service that needs no cleverness.

    What is being proved is not that the program failed -- it is that it
    failed at a number we chose, in this container, while the machine running
    the test carried on. The 64 in the limit is why the API is still up.
    """
    report, _ = attack("attack_fork_bomb.py")

    assert "ESCAPED" not in report
    assert "fork bomb stopped after" in report
    # EAGAIN: the kernel's way of saying this cgroup has had its share.
    assert "Resource temporarily unavailable" in report

    stopped_after = int(report.split("stopped after ")[1].split(" ")[0])
    assert 0 < stopped_after < ATTACK_LIMITS.pids


def test_the_submission_cannot_become_root_or_gain_a_capability():
    """The assumption every other test in this file rests on."""
    report, _ = attack("attack_escalate_privileges.py")

    assert "ESCAPED" not in report
    assert report.count("BLOCKED") == 9
    assert "uid=10001" in report
    # The kernel's own answer. All capabilities empty, and no way to acquire
    # one later even by executing something that would normally grant it.
    assert "CapEff:\t0000000000000000" in report
    assert "CapBnd:\t0000000000000000" in report
    assert "NoNewPrivs:\t1" in report


def test_the_one_writable_place_cannot_fill_the_hosts_disk():
    report, _ = attack("attack_fill_tmpfs.py")

    assert "ESCAPED" not in report
    assert "No space left on device" in report

    written = int(report.split("after ")[1].split(" MB")[0])
    assert written <= ATTACK_LIMITS.tmpfs_mb
