"""delete_quietly: forgive a failed clean-up, but leave a trace of it."""

import logging

import pytest

from app.services.storage import delete_quietly


class RefusingStorage:
    def delete_prefix(self, prefix: str) -> None:
        raise ConnectionError("bucket unreachable")


class RecordingStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_prefix(self, prefix: str) -> None:
        self.deleted.append(prefix)


def test_a_failed_delete_is_swallowed_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    """The caller just finished an upload; a stale object must not cost it that.
    Swallowing silently, though, is how a delete that always fails goes unseen."""
    with caplog.at_level(logging.WARNING, logger="app.services.storage"):
        delete_quietly(RefusingStorage(), "videos/42/")

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert "videos/42/" in record.getMessage()
    assert "bucket unreachable" in record.getMessage()


def test_a_successful_delete_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    storage = RecordingStorage()
    with caplog.at_level(logging.WARNING, logger="app.services.storage"):
        delete_quietly(storage, "avatars/7/")

    assert storage.deleted == ["avatars/7/"]
    assert caplog.records == []
