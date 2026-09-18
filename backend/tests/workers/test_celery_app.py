from app.core.config import get_settings
from app.workers.celery_app import GRADING_QUEUE, celery_app, ping


def test_broker_and_backend_come_from_settings() -> None:
    """Redis URL is configured in one place; Celery must not hardcode its own."""
    settings = get_settings()

    assert celery_app.conf.broker_url == settings.redis_url
    assert celery_app.conf.result_backend == settings.redis_url


def test_ping_task_is_registered() -> None:
    """The worker container is only proof of a working queue if a task exists."""
    assert "app.workers.celery_app.ping" in celery_app.tasks


def test_ping_returns_pong() -> None:
    assert ping() == "pong"


NIGHTLY = "app.workers.recommendations.rebuild_recommendations"


def test_the_worker_is_told_to_import_the_module_that_defines_the_rebuild() -> None:
    """`include` is what makes a task exist for the worker.

    A task named in `beat_schedule` but living in a module nobody imports is
    the worst shape this can take: beat publishes it every night, no worker
    recognises it, and every container still reports itself healthy.
    """
    assert "app.workers.recommendations" in celery_app.conf.include


def test_the_nightly_rebuild_registers_under_the_name_beat_publishes() -> None:
    """The name in `beat_schedule` and the name the decorator registers are
    the same string written in two files."""
    import app.workers.recommendations  # noqa: F401  -- what `include` does at startup

    assert NIGHTLY in celery_app.tasks


def test_the_nightly_rebuild_is_scheduled_once_a_night() -> None:
    entry = celery_app.conf.beat_schedule["rebuild-recommendations-nightly"]

    assert entry["task"] == NIGHTLY
    schedule = entry["schedule"]
    assert schedule.hour == {3} and schedule.minute == {0}
    # Beat resolves crontabs in the app's timezone, not the container's.
    assert celery_app.conf.timezone == "Asia/Ho_Chi_Minh"


def test_the_nightly_rebuild_stays_off_the_grading_queue() -> None:
    """Those cores belong to submissions somebody is watching a page for.

    With no route of its own the task goes to the default `celery` queue,
    which the media worker also consumes -- so this asserts the absence of a
    grading route rather than the presence of a new queue.
    """
    # kombu answers with a Queue object, not a name.
    queue = celery_app.amqp.router.route({}, NIGHTLY)["queue"]

    assert queue.name != GRADING_QUEUE
    assert queue.name == "celery"


INGEST = "app.workers.rag.ingest_course"


def test_the_worker_is_told_to_import_the_ingest_module() -> None:
    """Publishing a course enqueues this by name. A name no worker recognises
    fails on the worker's side, where nobody is looking -- the publish itself
    succeeds and the instructor sees nothing wrong."""
    assert "app.workers.rag" in celery_app.conf.include


def test_the_ingest_registers_under_the_name_the_api_enqueues() -> None:
    """`CeleryTaskQueue.enqueue_ingest` sends this task; the decorator names
    it. Two files, one string."""
    import app.workers.rag  # noqa: F401  -- what `include` does at startup

    assert INGEST in celery_app.tasks


def test_the_ingest_stays_off_the_grading_queue() -> None:
    """Ingest is a burst of waiting on Gemini. The grading cores belong to
    submissions somebody is watching a page for."""
    queue = celery_app.amqp.router.route({}, INGEST)["queue"]

    assert queue.name != GRADING_QUEUE
    assert queue.name == "celery"
