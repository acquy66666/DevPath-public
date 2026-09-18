"""Ingesting a course's text into `doc_chunks`, off the request path.

A thin wrapper, like the transcode and recommendation tasks: everything worth
testing is in `app.services.ingest.ingest_course`, which takes a session and an
embedder and knows nothing about Celery.

It runs on the **default queue**, with the recommendation batch, and stays off
`grading` for the reason that queue exists -- those cores belong to submissions
somebody is watching a page for. Ingest is a burst of network calls to Gemini,
which is mostly waiting, and nobody is watching it.

**Failures are not retried automatically.** The expected one is a quota limit,
and Celery's default retry would spend the next attempt on the same exhausted
key -- then again, and again, using the quota the ingest is waiting for. The
job commits lesson by lesson, so re-running it after the quota resets resumes
where it stopped and re-embeds nothing that already succeeded. Re-running it is
a button in the instructor's hands (publish) and a command in the operator's
(`python -m scripts.ingest_course`), which is a better answer than a retry
storm nobody can see.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.ingest import ingest_course
from app.services.llm import LLMError, build_embedder
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.rag.ingest_course")
def ingest_course_task(course_id: str) -> dict[str, int]:
    """Celery entry point. Owns the event loop and the database connection."""
    return asyncio.run(_run(course_id))


async def _run(course_id: str) -> dict[str, int]:
    import uuid

    try:
        embedder = build_embedder()
    except LLMError as error:
        # No key configured. Not an error worth failing the task over: the rest
        # of the platform works without a chatbot, and a red task on every
        # publish would train everyone to ignore red tasks.
        logger.warning("Bỏ qua ingest khóa %s: %s", course_id, error.message)
        return {"lessons": 0, "chunks": 0, "unchanged": 0, "skipped": 0, "removed": 0}

    # A fresh engine per run, like the other workers: the worker process is
    # synchronous, so there is no long-lived loop a pooled connection could
    # belong to.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            report = await ingest_course(
                session, uuid.UUID(course_id), embedder=embedder
            )
    finally:
        await engine.dispose()

    logger.info(
        "Ingest khóa %s: %d bài học, %d chunk, %d bài không đổi, %d bài bỏ qua, "
        "%d bài hết chữ đã gỡ chunk",
        course_id,
        report.lessons,
        report.chunks,
        report.unchanged,
        report.skipped,
        report.removed,
    )
    return {
        "lessons": report.lessons,
        "chunks": report.chunks,
        "unchanged": report.unchanged,
        "skipped": report.skipped,
        "removed": report.removed,
    }
