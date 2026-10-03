import asyncio
import time

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.services import readiness


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"]
    assert body["env"]


async def test_unknown_route_uses_the_shared_error_envelope(client: AsyncClient) -> None:
    """Every error must come back as {"detail": {"code", "message"}}."""
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "NOT_FOUND"
    assert detail["message"]


# --- Readiness ---------------------------------------------------------------


async def _fine() -> None:
    return None


async def _refused() -> None:
    # What asyncpg says when the database is gone: a host, a port and a user,
    # none of which a public endpoint should repeat.
    raise OSError("connect call failed ('10.9.8.7', 5432) for user devpath")


async def _hangs() -> None:
    await asyncio.sleep(30)


def _with_checks(app: FastAPI, **checks) -> None:
    app.dependency_overrides[readiness.get_readiness_checks] = lambda: checks


async def test_ready_when_the_database_and_redis_answer(
    client: AsyncClient, db_connection, real_redis_url: str
) -> None:
    """The real checks against the real services, nothing overridden."""
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }


async def test_not_ready_says_which_dependency_and_never_why(
    app: FastAPI, client: AsyncClient
) -> None:
    """503 in the shared error envelope, with a word per dependency.

    The word is all a probe needs. The exception -- hosts, ports, user names --
    goes to the log, because this endpoint answers anybody.
    """
    _with_checks(app, database=_refused, redis=_fine)

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "NOT_READY"
    assert detail["checks"] == {"database": "down", "redis": "ok"}
    assert "cơ sở dữ liệu" in detail["message"]
    assert "10.9.8.7" not in response.text
    assert "devpath" not in response.text


async def test_a_dependency_that_hangs_is_a_timeout_not_a_hang(
    app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A paused database accepts the connection and then says nothing.

    A probe that waits with it is a probe that times out on the caller's
    side instead of answering, which every uptime checker reads as "the
    whole site is down".
    """
    monkeypatch.setattr(readiness, "READINESS_TIMEOUT_SECONDS", 0.2)
    _with_checks(app, database=_fine, redis=_hangs)

    started = time.monotonic()
    response = await client.get("/api/v1/health/ready")

    assert time.monotonic() - started < 2
    assert response.status_code == 503
    assert response.json()["detail"]["checks"] == {"database": "ok", "redis": "timeout"}


async def test_the_checks_run_side_by_side(
    app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two dead dependencies cost one timeout, not two."""
    monkeypatch.setattr(readiness, "READINESS_TIMEOUT_SECONDS", 0.5)
    _with_checks(app, database=_hangs, redis=_hangs)

    started = time.monotonic()
    response = await client.get("/api/v1/health/ready")

    assert time.monotonic() - started < 0.95
    assert response.json()["detail"]["checks"] == {"database": "timeout", "redis": "timeout"}


async def test_liveness_does_not_care_that_the_dependencies_are_gone(
    app: FastAPI, client: AsyncClient
) -> None:
    """The two probes answer different questions, and a broken database must
    not turn the liveness answer red: a container healthcheck reads it, and
    the process is fine."""
    _with_checks(app, database=_refused, redis=_refused)

    assert (await client.get("/api/v1/health/ready")).status_code == 503
    assert (await client.get("/api/v1/health")).status_code == 200


@pytest.fixture
def real_redis_url() -> str:
    """The configured Redis if it answers, or a skip -- except in CI."""
    import os

    import redis
    from redis.exceptions import RedisError

    from app.core.config import get_settings

    url = get_settings().redis_url
    client = redis.Redis.from_url(url)
    try:
        client.ping()
    except RedisError as exc:
        if os.getenv("CI"):
            raise
        pytest.skip(f"Redis không chạy ({exc}). `docker compose up -d redis` trong infra/.")
    finally:
        client.close()
    return url
