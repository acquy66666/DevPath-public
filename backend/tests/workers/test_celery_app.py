from app.core.config import get_settings
from app.workers.celery_app import celery_app, ping


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
