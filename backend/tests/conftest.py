import os
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db import get_db
from app.main import create_app
from app.services import grading_events, leaderboard
from app.services.rate_limit import get_rate_limiter
from tests.api.fakes import AllowAllRateLimiter, MemoryLeaderboard


@pytest.fixture(autouse=True)
def silent_grading_channel(monkeypatch: pytest.MonkeyPatch) -> list:
    """Grading progress is announced to nobody unless a test asks for it.

    The worker publishes to Redis as it grades. Without this, every test that
    runs `run_grading` would open a connection to a real Redis -- reaching
    infrastructure that no test here is about, and on a developer machine that
    has one, publishing to live channels about rows this transaction is going
    to roll back. Returns the list it collected, for a test that wants to look.
    """
    published: list = []

    class Collector:
        def publish(self, event) -> None:
            published.append(event)

    monkeypatch.setattr(grading_events, "get_publisher", Collector)
    return published


@pytest.fixture(autouse=True)
def memory_board(monkeypatch: pytest.MonkeyPatch) -> MemoryLeaderboard:
    """The leaderboard is kept in a dictionary unless a test asks otherwise.

    Awards are pushed to it after every commit that pays XP -- from the API,
    the quiz service and the grading worker alike -- so without this, most of
    the suite would reach for a Redis that no test here is about.
    """
    board = MemoryLeaderboard()
    monkeypatch.setattr(leaderboard, "get_board", lambda: board)
    return board


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """In-process HTTP client — no server and no database required."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
async def db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """A connection with an open transaction that is always rolled back.

    Every test therefore starts from the same database state, and nothing a
    test writes survives it -- including on the developer's own dev database,
    which is the one `alembic upgrade head` has already been run against.
    """
    settings = get_settings()
    # NullPool: the engine is built and thrown away per test, so pooling would
    # only leave connections behind for the next event loop to trip over.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)

    try:
        connection = await engine.connect()
    except OSError as exc:
        await engine.dispose()
        if os.getenv("CI"):
            # In CI the database is part of the job: unreachable means broken,
            # and silently skipping would turn a red build green.
            raise
        pytest.skip(
            f"Postgres không chạy ({exc}). Chạy `docker compose up -d postgres` "
            "trong infra/ rồi chạy lại."
        )

    transaction = await connection.begin()
    try:
        yield connection
    finally:
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:
    """Session bound to the test transaction.

    `join_transaction_mode="create_savepoint"` turns the service layer's real
    `commit()` calls into savepoint releases, so the code under test commits
    exactly as it does in production while the outer rollback still wipes it.
    """
    session = AsyncSession(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def api_client(
    app: FastAPI, db_session: AsyncSession
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client whose requests run inside the test transaction."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # No Redis in an API test, and no cooldown either: a test that submits
    # twice is testing something else. The tests that *are* about the limit
    # override this again with one that counts.
    app.dependency_overrides[get_rate_limiter] = AllowAllRateLimiter
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()
