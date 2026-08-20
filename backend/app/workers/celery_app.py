"""Celery entrypoint. The worker container runs:

    celery -A app.workers.celery_app worker

Task modules are registered here as they appear (grading in Phase 3,
embedding and mail later); for now the queue only needs to prove itself.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "devpath",
    broker=settings.redis_url,
    backend=settings.redis_url,
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
