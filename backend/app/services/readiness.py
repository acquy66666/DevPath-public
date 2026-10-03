"""Whether the API can serve a request right now.

`/health` is liveness, and on purpose it touches nothing: the container
healthcheck reads it, and a process that is fine must not be reported sick
because Postgres is restarting. This module is the other question -- does the
database answer, does Redis answer -- asked by whoever is deciding whether the
site works: the deploy script before it says "deployed", and an uptime check
from outside.

Three rules shape it:

* **Bounded.** Each check gets `READINESS_TIMEOUT_SECONDS`, and they run side
  by side, so the answer comes back in about that long whatever is broken. A
  paused database accepts a connection and then says nothing; a probe that
  waits with it times out on the caller's side instead of answering.
* **Its own connections.** The database check opens one connection through an
  engine of its own rather than borrowing from the request pool: the question
  is whether Postgres answers, and cancelling a checkout half way through a
  connect is not something to do to the pool every request depends on.
* **A word per dependency, never the reason.** "down" or "timeout" is all a
  probe needs. The exception goes to the log, because this endpoint answers
  anybody and a connection error names hosts, ports and users.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from functools import lru_cache

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.exceptions import DomainError

logger = logging.getLogger(__name__)

#: Per check. Long enough for a database on a busy two-core VPS to answer
#: `SELECT 1`, short enough that an uptime checker with a 30-second timeout
#: always gets an answer rather than giving up on us.
READINESS_TIMEOUT_SECONDS = 2.0

OK = "ok"
DOWN = "down"
TIMEOUT = "timeout"

#: How the message names each dependency, for the person reading a 503.
_NAMES = {"database": "cơ sở dữ liệu", "redis": "Redis"}

Check = Callable[[], Awaitable[object]]


class NotReadyError(DomainError):
    status_code = 503
    code = "NOT_READY"

    def __init__(self, checks: Mapping[str, str]) -> None:
        failing = ", ".join(
            _NAMES.get(name, name) for name, result in checks.items() if result != OK
        )
        super().__init__(f"Hệ thống chưa sẵn sàng: {failing} không phản hồi.")
        self.extra = {"checks": dict(checks)}


@lru_cache
def _engine(url: str) -> AsyncEngine:
    # NullPool: a connection per check, closed after it. The `timeout` is
    # asyncpg's own connect timeout, so a host that never answers fails here
    # rather than being cancelled from outside.
    return create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"timeout": READINESS_TIMEOUT_SECONDS},
    )


async def check_database(url: str | None = None) -> None:
    """`SELECT 1` on a fresh connection, with the API's own credentials."""
    async with _engine(url or get_settings().database_url).connect() as connection:
        await connection.execute(text("SELECT 1"))


async def check_redis(url: str | None = None) -> None:
    """`PING` on a client of its own, closed after the answer."""
    client = aioredis.from_url(
        url or get_settings().redis_url,
        socket_connect_timeout=READINESS_TIMEOUT_SECONDS,
        socket_timeout=READINESS_TIMEOUT_SECONDS,
    )
    try:
        await client.ping()
    finally:
        await client.aclose()


def get_readiness_checks() -> dict[str, Check]:
    """FastAPI dependency. Tests override it with checks that fail on cue."""
    return {"database": check_database, "redis": check_redis}


async def probe(checks: Mapping[str, Check]) -> dict[str, str]:
    """Run every check at once and say how each one went."""

    async def one(name: str, check: Check) -> str:
        try:
            await asyncio.wait_for(check(), READINESS_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("readiness: %s did not answer in %ss", name, READINESS_TIMEOUT_SECONDS)
            return TIMEOUT
        except Exception as exc:  # noqa: BLE001 - any failure is "down"; the log says which
            logger.warning("readiness: %s is down: %s: %s", name, type(exc).__name__, exc)
            return DOWN
        return OK

    results = await asyncio.gather(*(one(name, check) for name, check in checks.items()))
    return dict(zip(checks, results, strict=True))


async def require_ready(checks: Mapping[str, Check]) -> dict[str, str]:
    """Every check's result, or `NotReadyError` naming the ones that failed."""
    results = await probe(checks)
    if any(result != OK for result in results.values()):
        raise NotReadyError(results)
    return results
