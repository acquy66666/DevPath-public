"""delete_quietly: forgive a failed clean-up, but leave a trace of it.

And the signed upload URL: what goes into the signature is what the bucket
will hold the browser to. These sign offline -- boto3 reaches no network to
presign -- and `docs/report/assets/phase-6/signed-upload-length/probe.py` asks
the real bucket whether it holds the browser to it.
"""

import datetime
import logging
from urllib.parse import parse_qs, urlsplit

import botocore.auth
import pytest

from app.services.storage import R2Storage, delete_quietly


def _bucket() -> R2Storage:
    return R2Storage(
        endpoint_url="http://bucket.test:9000",
        access_key_id="test-key",
        secret_access_key="test-secret",
        bucket="devpath-media",
        public_base_url="http://bucket.test:9000/devpath-media",
    )


def _query(url: str) -> dict[str, str]:
    return {name: values[0] for name, values in parse_qs(urlsplit(url).query).items()}


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two signatures a second apart differ for that reason alone."""
    moment = datetime.datetime(2026, 10, 16, 9, 30, 0)
    monkeypatch.setattr(botocore.auth, "get_current_datetime", lambda *a, **k: moment)


def test_an_upload_url_signs_the_size_and_the_type_in() -> None:
    """A header in SignedHeaders is one the bucket recomputes the signature
    from: a body of any other length, or sent chunked with no length at all,
    no longer matches. Without it a ticket for a 5 MB avatar takes 2 GB."""
    url = _bucket().presigned_put_url(
        "avatars/u/a.png", "image/png", 600, size_bytes=1234
    )

    assert _query(url)["X-Amz-SignedHeaders"] == "content-length;content-type;host"


def test_the_declared_size_is_what_gets_signed(frozen_clock: None) -> None:
    """Not just that a length is signed, but this one: a ticket for one size
    must not be good for another."""
    bucket = _bucket()

    def signature(size: int) -> str:
        url = bucket.presigned_put_url("avatars/u/a.png", "image/png", 600, size_bytes=size)
        return _query(url)["X-Amz-Signature"]

    assert signature(1234) == signature(1234)
    assert signature(1234) != signature(1235)


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
