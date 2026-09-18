"""Naming how a run ended, from the facts Docker hands back.

No Docker here, on purpose. The case this suite exists for is Docker itself
being unreliable: a container the kernel killed for memory sometimes comes back
with `State.OOMKilled` false -- seen on CI runners, never on the dev machine --
and a real container cannot be made to do that on demand. So the facts are
stated as values and the rule is checked against them.

The rule those facts support: a SIGKILL that arrives before the CPU limit could
possibly have been spent was not the CPU limit. The container gets `cpus` of a
core, so N seconds of CPU cost at least N / cpus seconds of wall time, and the
hard stop comes one CPU second after the soft one. The lifetime read is the
container's own, from Docker's StartedAt/FinishedAt, and includes init and
interpreter startup, so it can only overstate how long the program ran -- which
means the rule can only ever fall back to calling a real time limit a time
limit, never the other way round.
"""

from __future__ import annotations

import pytest

from runner.sandbox import Limits, Outcome, classify, container_lifetime

# The limits the container suite runs with: one CPU second on half a core, so
# the soft limit cannot arrive before 2 s of wall time and the hard one not
# before 4 s.
QUICK = Limits(cpu_seconds=1, startup_grace_seconds=2.0)


def test_a_memory_kill_is_named_even_when_docker_forgets_to_say_so():
    """The flake from PR #29, #30 and a run on main, with its exact signature.

    exit 137 after a quarter of a second, flag false. The CPU limit's SIGKILL
    needs two CPU seconds, which on half a core is 4 s of wall time at the
    least, so it was not the CPU limit's -- and a student whose program ran out
    of memory must not be told it was too slow.
    """
    ended = classify(137, oom_killed=False, hit_the_wall=False, lifetime_seconds=0.26, limits=QUICK)

    assert ended is Outcome.OUT_OF_MEMORY


def test_a_slow_memory_kill_between_the_two_cpu_limits_is_still_a_memory_kill():
    """The slowest memory kill measured on the dev machine: 2.37 s.

    Docker Desktop takes its time reaching for the OOM killer, and 2.37 s is
    past the soft limit's 2 s. That does not make it the CPU limit: the soft
    limit ends a program with SIGXCPU (152), and a program that survives it is
    only SIGKILLed at the hard limit, 4 s. A 137 in between is nobody's but
    the memory limit's. The 1-second CPU limit is not test-only either --
    instructors can set anything from 100 ms, which rounds up to it.
    """
    ended = classify(137, oom_killed=False, hit_the_wall=False, lifetime_seconds=2.37, limits=QUICK)

    assert ended is Outcome.OUT_OF_MEMORY


def test_a_program_that_outlived_its_cpu_limit_is_still_a_time_limit():
    """The case the rule must not swallow: a program that caught SIGXCPU.

    It kept running until the hard limit, which on these limits cannot happen
    before 4 s. Exit 137 at 4.5 s is exactly what that looks like.
    """
    ended = classify(137, oom_killed=False, hit_the_wall=False, lifetime_seconds=4.5, limits=QUICK)

    assert ended is Outcome.CPU_TIME_EXCEEDED


def test_how_early_is_too_early_follows_the_limits_the_program_ran_with():
    """Four and a half seconds is long under QUICK and short under the defaults.

    With five CPU seconds on half a core, the CPU limit's SIGKILL cannot come
    before 12 s, so one at 4.5 s can only have been the memory limit. Under
    QUICK the same 4.5 s is past the hard limit. A threshold fixed at one
    number would get one of these two wrong.
    """
    defaults = Limits()

    assert (
        classify(137, oom_killed=False, hit_the_wall=False, lifetime_seconds=4.5, limits=defaults)
        is Outcome.OUT_OF_MEMORY
    )
    assert (
        classify(137, oom_killed=False, hit_the_wall=False, lifetime_seconds=4.5, limits=QUICK)
        is Outcome.CPU_TIME_EXCEEDED
    )


@pytest.mark.parametrize(
    ("exit_code", "oom_killed", "hit_the_wall", "lifetime_seconds", "expected"),
    [
        # Docker did say so: believed, whenever it happened.
        (137, True, False, 0.26, Outcome.OUT_OF_MEMORY),
        (137, True, False, 4.5, Outcome.OUT_OF_MEMORY),
        # The outer clock fired. `docker kill` also exits 137, and it is the
        # wall clock's stop, not the memory limit's.
        (137, False, True, 6.1, Outcome.WALL_TIME_EXCEEDED),
        # SIGXCPU is only ever the CPU limit, however early it looks.
        (152, False, False, 0.26, Outcome.CPU_TIME_EXCEEDED),
        (152, False, False, 2.5, Outcome.CPU_TIME_EXCEEDED),
        # A program that reached its own end, right or wrong.
        (0, False, False, 0.05, Outcome.EXITED),
        (1, False, False, 0.05, Outcome.EXITED),
    ],
)
def test_the_other_endings_keep_their_names(
    exit_code, oom_killed, hit_the_wall, lifetime_seconds, expected
):
    ended = classify(
        exit_code,
        oom_killed=oom_killed,
        hit_the_wall=hit_the_wall,
        lifetime_seconds=lifetime_seconds,
        limits=QUICK,
    )

    assert ended is expected


def test_a_container_lifetime_is_read_from_dockers_own_clock():
    """Docker's two timestamps, nanoseconds and all, as seconds between them.

    This, not the worker's stopwatch, is what the rule above reads: the
    stopwatch also times `docker start` itself -- about a second on Docker
    Desktop, and more on a busy host -- which is enough to carry an early
    memory kill past the threshold and back into a time limit.
    """
    lived = container_lifetime("2026-09-18T10:00:00.100000000Z", "2026-09-18T10:00:02.350123456Z")

    assert lived == pytest.approx(2.250123)


@pytest.mark.parametrize(
    ("started_at", "finished_at"),
    [
        # Docker's zero time: what FinishedAt says for a container that never
        # finished. A lifetime computed from it is minus two thousand years.
        ("2026-09-18T10:00:00.1Z", "0001-01-01T00:00:00Z"),
        ("", ""),
        ("not a time", "2026-09-18T10:00:02Z"),
        # A clock that went backwards is not a lifetime either.
        ("2026-09-18T10:00:02Z", "2026-09-18T10:00:00Z"),
    ],
)
def test_a_lifetime_docker_cannot_vouch_for_is_unknown(started_at, finished_at):
    assert container_lifetime(started_at, finished_at) is None
