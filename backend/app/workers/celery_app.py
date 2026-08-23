"""Celery entrypoint. The worker container runs:

    celery -A app.workers.celery_app worker

Task modules are registered in `include` below as they appear -- video
transcoding now, grading in Phase 3, embedding and mail later.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "devpath",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Task modules the worker imports on start. A task that is never imported
    # is never registered, and Celery answers the enqueue with
    # "unregistered task" long after the code looked correct.
    include=["app.workers.video"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    # Grading jobs are long and must not be lost if a worker dies mid-run,
    # so a task is acknowledged only after it finishes.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task
def ping() -> str:
    """Smoke test for the broker connection — used by the compose healthcheck."""
    return "pong"
