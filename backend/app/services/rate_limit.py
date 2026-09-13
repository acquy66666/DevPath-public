"""How often one person may ask the platform to do expensive work.

The expensive work in question is grading: every submission starts containers,
holds a core and takes seconds. A loop pressing submit costs the queue far
more than it costs the person running it, and the students waiting behind them
pay for it -- so the limit exists to protect the queue, not to discipline
anyone.

Two shapes, because they answer two different abuses:

* `claim` -- one action per key per N seconds. A double-clicked button, or a
  script hammering one exercise.
* `count` -- so many actions per key per window. A patient script that waits
  out the cooldown, and the one thing a cooldown alone cannot stop.

Redis holds both, because the API runs as several processes and a counter in
Python memory would give each of them its own idea of the limit.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Protocol

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: Seconds the caller must wait. Zero means go ahead.
ALLOWED = 0


class RateLimiter(Protocol):
    """What the service layer needs. A Protocol so tests can hand it a
    dictionary and the routes can be exercised without Redis."""

    async def claim(self, key: str, seconds: int) -> int:
        """Take `key` for `seconds`. Returns 0 if it was free, else the wait."""
        ...

    async def count(self, key: str, limit: int, window_seconds: int) -> int:
        """Count one action against `limit` per window. 0 while under it."""
        ...


class RedisRateLimiter:
    """Both limits in single commands, so two processes cannot both win.

    `SET NX EX` and `INCR` are atomic in Redis. Read-then-write would not be:
    two requests from the same double-click land on two API workers, both read
    "nothing yet", and both go through.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    async def claim(self, key: str, seconds: int) -> int:
        try:
            if await self._redis.set(key, "1", nx=True, ex=seconds):
                return ALLOWED
            # Note what is *not* here: no second SET. A refused attempt must
            # not push the deadline back, or an impatient double-click would
            # keep renewing its own ban.
            return await self._time_left(key, seconds)
        except RedisError as exc:
            return self._fail_open(exc)

    async def count(self, key: str, limit: int, window_seconds: int) -> int:
        try:
            used = await self._redis.incr(key)
            if used == 1:
                # First of the window: give the counter its lifetime. Until
                # this lands the key has none, which `_time_left` repairs.
                await self._redis.expire(key, window_seconds)
            if used <= limit:
                return ALLOWED
            return await self._time_left(key, window_seconds)
        except RedisError as exc:
            return self._fail_open(exc)

    async def _time_left(self, key: str, fallback: int) -> int:
        ttl = await self._redis.ttl(key)
        if ttl < 0:
            # -1 is a key with no expiry: an INCR whose EXPIRE never landed,
            # which would lock this caller out for good. -2 is a key that
            # expired between the two calls. Either way, give it a lifetime.
            await self._redis.expire(key, fallback)
            return fallback
        # Never 0: that reads as "go ahead" to the caller.
        return max(ttl, 1)

    def _fail_open(self, exc: RedisError) -> int:
        """Let the request through when the limiter itself is broken.

        A narrow decision, not a general one. Redis is also the Celery broker,
        so a Redis that cannot answer here cannot take the job either: the
        request this waves through gets a 503 from the enqueue a few lines
        later. Refusing instead would turn a cache outage into "nobody can
        submit", in order to protect a queue that is not running.
        """
        logger.warning("rate limiter unavailable, letting the request through: %s", exc)
        return ALLOWED


@lru_cache
def _shared_limiter() -> RedisRateLimiter:
    # redis-py connects lazily, so building this costs nothing until the first
    # command -- and the pool behind it is shared by every request.
    client = redis.from_url(get_settings().redis_url, decode_responses=True)
    return RedisRateLimiter(client)


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency. Tests override this; nothing else builds a client."""
    return _shared_limiter()
