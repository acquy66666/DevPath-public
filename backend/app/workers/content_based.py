"""Keeping `course_embeddings` in step with the catalogue, off the request path.

A thin wrapper, like the transcode, recommendation and ingest tasks:
everything worth testing is in `app.services.content_based.rebuild_embeddings`,
which takes a session and an embedder and knows nothing about Celery.

**Two callers, one task.** Publishing a course enqueues it with that course's
id, because the instructor has just pressed a button and should not wait until
03:00 to see their course under "Khóa học tương tự". The nightly beat enqueues
it with no id at all, which checks the whole catalogue -- that is what catches
a course whose title or description was edited without being republished,
since a `PATCH` changes the words without touching the status.

It runs on the **default queue**, with the recommendation batch and the ingest,
and stays off `grading` for the reason that queue exists.

**Failures are not retried automatically**, for the same reason as the ingest:
the expected failure is a quota limit, and Celery's default retry would spend
the next attempt on the same exhausted key. The rebuild commits as it goes, so
re-running it after the quota resets re-embeds nothing that already succeeded.
"""

import asyncio
import logging
import uuid
from dataclasses import asdict

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.content_based import EmbeddingReport, rebuild_embeddings
from app.services.llm import LLMError, build_embedder
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.content_based.embed_courses")
def embed_courses_task(course_id: str | None = None) -> dict[str, int]:
    """Celery entry point. Owns the event loop and the database connection."""
    return asyncio.run(_run(course_id))


async def _run(course_id: str | None) -> dict[str, int]:
    try:
        embedder = build_embedder()
    except LLMError as error:
        # No key configured. Not worth failing the task over: the rest of the
        # platform works without a similar-courses block, and a red task on
        # every publish would train everyone to ignore red tasks.
        logger.warning("Bỏ qua nhúng khóa học: %s", error.message)
        return asdict(EmbeddingReport(embedded=0, unchanged=0))

    # A fresh engine per run, like the other workers: the worker process is
    # synchronous, so there is no long-lived loop a pooled connection could
    # belong to.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            report = await rebuild_embeddings(
                session,
                embedder=embedder,
                course_ids=[uuid.UUID(course_id)] if course_id else None,
            )
    finally:
        await engine.dispose()

    logger.info(
        "Nhúng khóa học (%s): %d khóa đã nhúng, %d khóa không đổi",
        course_id or "toàn bộ catalogue",
        report.embedded,
        report.unchanged,
    )
    return asdict(report)
