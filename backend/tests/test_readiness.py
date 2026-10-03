"""The readiness checks against services that are not there.

The API tests swap the checks for fakes; these run the real ones against a
port nothing listens on. Refused has to come back as a failure, and at once
-- "down", not a wait that ends as "timeout".
"""

import time

import pytest

from app.services import readiness

NOBODY = "127.0.0.1:1"


async def test_the_database_check_fails_when_nothing_answers() -> None:
    started = time.monotonic()
    with pytest.raises(OSError):
        await readiness.check_database(f"postgresql+asyncpg://devpath:x@{NOBODY}/devpath")
    assert time.monotonic() - started < 1


async def test_the_redis_check_fails_at_once_when_nothing_answers() -> None:
    from redis.exceptions import ConnectionError as RedisConnectionError

    started = time.monotonic()
    with pytest.raises(RedisConnectionError):
        await readiness.check_redis(f"redis://{NOBODY}/0")
    assert time.monotonic() - started < 1


async def test_a_refused_dependency_reads_as_down() -> None:
    checks = {
        "database": lambda: readiness.check_database(
            f"postgresql+asyncpg://devpath:x@{NOBODY}/devpath"
        ),
        "redis": lambda: readiness.check_redis(f"redis://{NOBODY}/0"),
    }

    assert await readiness.probe(checks) == {"database": "down", "redis": "down"}
