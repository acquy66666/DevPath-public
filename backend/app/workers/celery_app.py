"""Celery entrypoint. The worker containers run:

    celery -A app.workers.celery_app worker -Q media      # transcoding
    celery -A app.workers.celery_app worker -Q grading    # submissions

Two queues, two worker processes, because the two jobs are nothing alike. A
transcode is one ffmpeg run that can hold a core for half an hour; a grading
job is a handful of short containers that a student is watching the page for.
Sharing one queue would let a single uploaded lecture put every submission
behind it -- and the fair-sounding fix, more workers, would instead let a busy
afternoon start thirty containers on a two-core VPS.

Task modules are registered in `include` below as they appear -- embedding and
mail later.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Named here rather than in each task module: the queue a task is routed to
# and the queue a worker listens on are the same string in two files, and the
# failure when they differ is a job that sits in Redis forever while every
# container reports itself healthy.
GRADING_QUEUE = "grading"
MEDIA_QUEUE = "media"

celery_app = Celery(
    "devpath",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Task modules the worker imports on start. A task that is never imported
    # is never registered, and Celery answers the enqueue with
    # "unregistered task" long after the code looked correct.
    include=["app.workers.video", "app.workers.grading"],
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
    # The other half of acks_late: without this, a worker killed by the OOM
    # reaper -- the way a grading worker dies -- takes its job with it, because
    # only an *exception* counts as a failure by default. With it, the broker
    # redelivers, and `run_grading` is written to be safe to run twice.
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.grading.*": {"queue": GRADING_QUEUE},
        "app.workers.video.*": {"queue": MEDIA_QUEUE},
    },
)


@celery_app.task
def ping() -> str:
    """Smoke test for the broker connection — used by the compose healthcheck."""
    return "pong"
