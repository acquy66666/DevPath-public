"""Drawing certificate PDFs, off the request that issued them.

A thin wrapper like the other tasks: `app.services.certificates.render` does
the work and knows nothing about Celery. Default queue -- the media worker
consumes it -- because a PDF is a second of layout that nobody is waiting on
the page for, and the grading queue's cores are not this job's to borrow.

Storage failures are retried a few times; after that the certificate simply
has no PDF yet, and the first download that finds it missing queues it again.
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.certificates import render
from app.services.storage import StorageError, build_storage
from app.workers.celery_app import celery_app


@celery_app.task(
    name="app.workers.certificates.render_certificate",
    autoretry_for=(StorageError,),
    retry_backoff=30,
    max_retries=3,
)
def render_certificate(certificate_id: str) -> bool:
    return asyncio.run(_run(uuid.UUID(certificate_id)))


async def _run(certificate_id: uuid.UUID) -> bool:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await render(session, build_storage(), certificate_id)
    finally:
        await engine.dispose()
