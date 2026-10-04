"""The nightly orphan sweep of the media bucket.

A thin wrapper like the leaderboard rebuild: the rules live in
`app.services.orphans.sweep`, which knows nothing about Celery. Default queue
-- one bucket listing and a few queries a night.

Never forced: a night the valve stops is logged as an error and waits for a
person (`python -m scripts.sweep_orphans`). A deployment with no bucket
configured has nothing to sweep and says so instead of failing.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.orphans import sweep
from app.services.storage import StorageNotConfiguredError, build_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.orphans.sweep_orphans")
def sweep_orphans() -> str:
    try:
        storage = build_storage()
    except StorageNotConfiguredError:
        return "storage not configured"
    lines = asyncio.run(_run(storage))
    for line in lines:
        logger.info("orphan sweep: %s", line)
    return "; ".join(lines)


async def _run(storage) -> list[str]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            report = await sweep(session, storage, apply=True)
            return report.lines()
    finally:
        await engine.dispose()
