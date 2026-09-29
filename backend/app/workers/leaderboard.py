"""The nightly rebuild of the XP leaderboard from the ledger.

Increments after each commit keep the boards current; this is what keeps them
*right*. Anything an outage swallowed, an award that raced a rebuild, a user
deleted with their XP -- one pass over `xp_events` puts the week's, the
month's and the all-time board back to exactly what the ledger says.

A thin wrapper like the recommendation batch: the logic is
`app.services.leaderboard.rebuild_current`, which knows nothing about Celery.
Default queue, for the reason given there -- it is a few queries a night.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.leaderboard import get_board, rebuild_current
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.leaderboard.rebuild_leaderboards")
def rebuild_leaderboards() -> dict[str, int]:
    return asyncio.run(_run())


async def _run() -> dict[str, int]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await rebuild_current(session, get_board())
    finally:
        await engine.dispose()
