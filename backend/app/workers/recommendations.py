"""The nightly job that fills the recommendation cache.

A thin wrapper, like the transcode task: everything worth testing lives in
`app.services.recommendations.rebuild`, which takes a session and a writer and
knows nothing about Celery.

It runs on the **default queue**, not a new one. `docker-compose.yml` has the
media worker listening on `media,celery` precisely so a task added later has a
consumer without a new container, and this job fits that: it is a few seconds
of arithmetic once a night, not something a student is waiting for. It stays
off the grading queue for the reason that queue exists -- those cores belong to
submissions somebody is watching a page for.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.recommendations import build_writer, rebuild
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.recommendations.rebuild_recommendations")
def rebuild_recommendations() -> int:
    """Celery entry point. Owns the event loop and the database connection."""
    return asyncio.run(_run())


async def _run() -> int:
    # A fresh engine per run, for the same reason the transcode task builds
    # one: the worker is synchronous, so there is no long-lived loop a pooled
    # connection could belong to.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await rebuild(session, build_writer())
    finally:
        await engine.dispose()
