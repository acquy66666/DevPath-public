"""Handing work to the Celery worker.

Behind a Protocol for the same reason as storage: an API test should not need
a running broker to prove that finishing an upload schedules a transcode. The
tests assert against a fake that records what was enqueued.
"""

import uuid
from typing import Protocol


class TaskQueue(Protocol):
    def enqueue_transcode(self, video_asset_id: uuid.UUID) -> None: ...

    def enqueue_ingest(self, course_id: uuid.UUID) -> None: ...


class CeleryTaskQueue:
    """The real one. Imported lazily so the API process only pulls in the
    worker module when it actually schedules something."""

    def enqueue_transcode(self, video_asset_id: uuid.UUID) -> None:
        from app.workers.video import transcode_video

        transcode_video.delay(str(video_asset_id))

    def enqueue_ingest(self, course_id: uuid.UUID) -> None:
        from app.workers.rag import ingest_course_task

        ingest_course_task.delay(str(course_id))


def get_task_queue() -> TaskQueue:
    """FastAPI dependency. Tests override this."""
    return CeleryTaskQueue()
