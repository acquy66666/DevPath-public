"""The rate limiter, against a Redis that lives in a dictionary.

Two questions only: does it count correctly, and what does it do when Redis is
not there. The second one matters more than it looks -- a limiter that refuses
everything when its own storage is down turns a cache outage into an outage of
the feature it was supposed to protect.
"""

import os
import uuid

import pytest
import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.services.rate_limit import ALLOWED, RedisRateLimiter

COOLDOWN = 10
WINDOW = 3600
LIMIT = 3


class FakeRedis:
    """Just enough Redis: SET NX EX, INCR, EXPIRE, TTL, on a fake clock."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expiry: dict[str, int] = {}
        self.now = 0

    def _evict(self) -> None:
        for key, expires_at in list(self.expiry.items()):
            if expires_at <= self.now:
                self.values.pop(key, None)
                self.expiry.pop(key, None)

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int = 0):
        self._evict()
        if nx and key in self.values:
            return None
        self.values[key] = int(value)
        if ex:
            self.expiry[key] = self.now + ex
        return True

    async def incr(self, key: str) -> int:
        self._evict()
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self._evict()
        if key not in self.values:
            return False
        self.expiry[key] = self.now + seconds
        return True

    async def ttl(self, key: str) -> int:
        self._evict()
        if key not in self.values:
            return -2  # what Redis answers for a key that is not there
        if key not in self.expiry:
            return -1  # ... and for one that will never expire
        return self.expiry[key] - self.now


class BrokenRedis(FakeRedis):
    async def set(self, *args, **kwargs):
        raise RedisConnectionError("redis is down")

    async def incr(self, key: str) -> int:
        raise RedisConnectionError("redis is down")


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def limiter(fake_redis: FakeRedis) -> RedisRateLimiter:
    return RedisRateLimiter(fake_redis)


# --- One at a time ----------------------------------------------------------


async def test_the_first_claim_goes_through(limiter: RedisRateLimiter) -> None:
    assert await limiter.claim("submit:1", COOLDOWN) == ALLOWED


async def test_the_second_claim_is_told_how_long_to_wait(
    limiter: RedisRateLimiter, fake_redis: FakeRedis
) -> None:
    await limiter.claim("submit:1", COOLDOWN)
    fake_redis.now += 4

    assert await limiter.claim("submit:1", COOLDOWN) == COOLDOWN - 4


async def test_the_claim_frees_itself_when_the_wait_is_over(
    limiter: RedisRateLimiter, fake_redis: FakeRedis
) -> None:
    await limiter.claim("submit:1", COOLDOWN)
    fake_redis.now += COOLDOWN

    assert await limiter.claim("submit:1", COOLDOWN) == ALLOWED


async def test_a_refused_claim_does_not_extend_the_wait(
    limiter: RedisRateLimiter, fake_redis: FakeRedis
) -> None:
    """Otherwise an impatient double-click locks someone out for good.

    The point of the cooldown is to space submissions out, not to punish the
    person who pressed the button twice.
    """
    await limiter.claim("submit:1", COOLDOWN)
    fake_redis.now += 9
    await limiter.claim("submit:1", COOLDOWN)
    fake_redis.now += 1

    assert await limiter.claim("submit:1", COOLDOWN) == ALLOWED


async def test_two_keys_do_not_share_a_cooldown(limiter: RedisRateLimiter) -> None:
    await limiter.claim("submit:1", COOLDOWN)

    assert await limiter.claim("submit:2", COOLDOWN) == ALLOWED


# --- So many per window -----------------------------------------------------


async def test_the_quota_allows_exactly_the_limit(limiter: RedisRateLimiter) -> None:
    for _ in range(LIMIT):
        assert await limiter.count("hour:1", LIMIT, WINDOW) == ALLOWED

    assert await limiter.count("hour:1", LIMIT, WINDOW) > 0


async def test_the_quota_says_when_the_window_resets(
    limiter: RedisRateLimiter, fake_redis: FakeRedis
) -> None:
    for _ in range(LIMIT):
        await limiter.count("hour:1", LIMIT, WINDOW)
    fake_redis.now += 600

    assert await limiter.count("hour:1", LIMIT, WINDOW) == WINDOW - 600


async def test_the_window_starts_over(
    limiter: RedisRateLimiter, fake_redis: FakeRedis
) -> None:
    for _ in range(LIMIT + 2):
        await limiter.count("hour:1", LIMIT, WINDOW)
    fake_redis.now += WINDOW

    assert await limiter.count("hour:1", LIMIT, WINDOW) == ALLOWED


async def test_a_counter_that_lost_its_expiry_gets_one_back(
    limiter: RedisRateLimiter, fake_redis: FakeRedis
) -> None:
    """A crash between INCR and EXPIRE would otherwise be permanent.

    The key would sit there with no TTL, over the limit, and that user could
    never submit again -- a bug that only appears days later and looks like
    the account being broken.
    """
    fake_redis.values["hour:1"] = LIMIT + 1  # counted, never given a TTL
    assert await fake_redis.ttl("hour:1") == -1

    wait = await limiter.count("hour:1", LIMIT, WINDOW)

    assert wait == WINDOW
    assert await fake_redis.ttl("hour:1") == WINDOW


# --- When Redis is not there ------------------------------------------------


async def test_a_dead_redis_does_not_stop_anyone_from_submitting() -> None:
    """Fail open, deliberately, and it is a narrow decision rather than a
    general one.

    Redis is also the Celery broker: when it is down, the submission that this
    limiter just waved through cannot be queued either, and the API answers
    503 a few lines later. Refusing here would trade "the queue is unprotected
    for a moment" for "nobody can submit", to protect a queue that is not
    running.
    """
    limiter = RedisRateLimiter(BrokenRedis())

    assert await limiter.claim("submit:1", COOLDOWN) == ALLOWED
    assert await limiter.count("hour:1", LIMIT, WINDOW) == ALLOWED


# --- Against the real thing -------------------------------------------------


@pytest.fixture
async def real_redis():
    """A live Redis, or a skip -- except in CI, where it is part of the job.

    The tests above prove the rules; this one proves the four commands are
    spelled the way redis-py expects them. A typo in `nx=True` reads fine and
    would only ever show up as a rate limit that does not limit.
    """
    client = redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await client.ping()
    except RedisError as exc:
        await client.aclose()
        if os.getenv("CI"):
            raise
        pytest.skip(f"Redis không chạy ({exc}). `docker compose up -d redis` trong infra/.")

    yield client
    await client.aclose()


async def test_the_real_client_understands_the_same_four_commands(real_redis) -> None:
    limiter = RedisRateLimiter(real_redis)
    cooldown_key = f"rl:test:cooldown:{uuid.uuid4().hex}"
    window_key = f"rl:test:window:{uuid.uuid4().hex}"

    try:
        assert await limiter.claim(cooldown_key, 30) == ALLOWED
        wait = await limiter.claim(cooldown_key, 30)
        assert 0 < wait <= 30

        assert await limiter.count(window_key, 1, 30) == ALLOWED
        wait = await limiter.count(window_key, 1, 30)
        assert 0 < wait <= 30
        # The counter got a lifetime, so a refused caller is not refused forever.
        assert await real_redis.ttl(window_key) > 0
    finally:
        await real_redis.delete(cooldown_key, window_key)
