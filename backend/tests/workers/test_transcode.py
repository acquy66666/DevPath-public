"""The transcode step, without Celery and mostly without ffmpeg.

`transcode()` takes a session and a storage, so the orchestration -- download,
convert, upload, record -- is testable on its own. One test at the bottom does
run the real ffmpeg, and skips itself where there is none.
"""

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VideoAsset
from app.workers import video as worker
from app.workers.video import TranscodeError, transcode

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class FakeStorage:
    """A bucket in a dictionary. `download_file` writes a real file, because
    the code under test hands that path to ffmpeg."""

    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.downloaded: list[str] = []

    def presigned_put_url(self, key: str, content_type: str, expires_in: int) -> str:
        return f"https://bucket.example/{key}"

    def public_url(self, key: str) -> str:
        return f"https://cdn.example/{key}"

    def download_file(self, key: str, destination: str) -> None:
        self.downloaded.append(key)
        Path(destination).write_bytes(b"not really a video")

    def upload_file(self, source: str, key: str, content_type: str | None = None) -> None:
        self.uploaded.append(key)

    def delete_prefix(self, prefix: str) -> None:
        pass


class BrokenStorage(FakeStorage):
    def download_file(self, key: str, destination: str) -> None:
        raise RuntimeError("bucket không phản hồi")


@pytest.fixture
def fake_ffmpeg(monkeypatch: pytest.MonkeyPatch):
    """Write what ffmpeg would have written, without spending a minute on it."""

    def _run(source: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = output_dir / worker.MANIFEST_NAME
        manifest.write_text("#EXTM3U\n#EXT-X-ENDLIST\n", encoding="utf-8")
        (output_dir / "segment_0000.ts").write_bytes(b"segment one")
        (output_dir / "segment_0001.ts").write_bytes(b"segment two")
        return manifest

    monkeypatch.setattr(worker, "run_ffmpeg", _run)
    monkeypatch.setattr(worker, "probe_duration_seconds", lambda source: 754)


async def make_asset(session: AsyncSession, status: str = "processing") -> VideoAsset:
    asset = VideoAsset(
        id=uuid.uuid4(), storage_key="videos/x/original.mp4", status=status
    )
    asset.storage_key = f"videos/{asset.id}/original.mp4"
    session.add(asset)
    await session.flush()
    return asset


async def test_a_finished_transcode_is_ready_and_playable(
    db_session: AsyncSession, fake_ffmpeg: None
) -> None:
    asset = await make_asset(db_session)
    storage = FakeStorage()

    result = await transcode(db_session, storage, asset.id)

    assert result == "ready"
    await db_session.refresh(asset)
    assert asset.status == "ready"
    assert asset.hls_manifest_key == f"videos/{asset.id}/hls/index.m3u8"
    assert asset.duration_s == 754
    assert asset.error_message is None


async def test_every_segment_is_uploaded_next_to_its_manifest(
    db_session: AsyncSession, fake_ffmpeg: None
) -> None:
    """A manifest without its segments is a video that fails halfway through."""
    asset = await make_asset(db_session)
    storage = FakeStorage()

    await transcode(db_session, storage, asset.id)

    prefix = f"videos/{asset.id}/hls"
    assert sorted(storage.uploaded) == [
        f"{prefix}/index.m3u8",
        f"{prefix}/segment_0000.ts",
        f"{prefix}/segment_0001.ts",
    ]
    assert storage.downloaded == [asset.storage_key]


async def test_a_video_ffmpeg_refuses_ends_as_failed_with_a_readable_reason(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = await make_asset(db_session)

    def _boom(source: Path, output_dir: Path) -> Path:
        raise TranscodeError("ffmpeg thất bại: Invalid data found when processing input")

    monkeypatch.setattr(worker, "run_ffmpeg", _boom)

    result = await transcode(db_session, FakeStorage(), asset.id)

    assert result == "failed"
    await db_session.refresh(asset)
    assert asset.status == "failed"
    assert "Invalid data" in (asset.error_message or "")
    # Nothing half-finished is advertised as playable.
    assert asset.hls_manifest_key is None


async def test_a_bucket_that_will_not_answer_fails_the_asset_rather_than_the_worker(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raised exception would be retried forever and read by nobody."""
    asset = await make_asset(db_session)
    monkeypatch.setattr(worker, "probe_duration_seconds", lambda source: None)

    result = await transcode(db_session, BrokenStorage(), asset.id)

    assert result == "failed"
    await db_session.refresh(asset)
    assert "bucket không phản hồi" in (asset.error_message or "")


async def test_an_error_message_never_grows_past_the_column(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = await make_asset(db_session)
    monkeypatch.setattr(
        worker,
        "run_ffmpeg",
        lambda source, output_dir: (_ for _ in ()).throw(TranscodeError("x" * 5000)),
    )

    await transcode(db_session, FakeStorage(), asset.id)

    await db_session.refresh(asset)
    assert len(asset.error_message or "") == worker.ERROR_MESSAGE_MAX_LENGTH


async def test_a_redelivered_job_leaves_a_finished_video_alone(
    db_session: AsyncSession, fake_ffmpeg: None
) -> None:
    """Celery redelivers when a worker dies; running twice would republish."""
    asset = await make_asset(db_session, status="ready")
    asset.hls_manifest_key = "videos/old/hls/index.m3u8"
    await db_session.flush()
    storage = FakeStorage()

    result = await transcode(db_session, storage, asset.id)

    assert result == "ready"
    assert storage.downloaded == []
    assert storage.uploaded == []
    await db_session.refresh(asset)
    assert asset.hls_manifest_key == "videos/old/hls/index.m3u8"


async def test_an_asset_that_no_longer_exists_is_not_an_error(
    db_session: AsyncSession, fake_ffmpeg: None
) -> None:
    """The lesson can be deleted while the job sits in the queue."""
    assert await transcode(db_session, FakeStorage(), uuid.uuid4()) == "missing"


async def test_the_workspace_is_cleaned_up(
    db_session: AsyncSession, fake_ffmpeg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker that leaves its temp files behind fills the disk in a week."""
    asset = await make_asset(db_session)
    created: list[str] = []

    original = worker._make_workspace

    def _record(video_asset_id: uuid.UUID) -> str:
        path = original(video_asset_id)
        created.append(path)
        return path

    monkeypatch.setattr(worker, "_make_workspace", _record)

    await transcode(db_session, FakeStorage(), asset.id)

    assert created and not Path(created[0]).exists()


# --- The real thing --------------------------------------------------------


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe không có trên máy này")
def test_ffmpeg_really_produces_a_playable_manifest(tmp_path: Path) -> None:
    """Proves the actual command line works -- the flags are easy to get wrong
    and a fake would happily agree with a broken one."""
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            str(source),
        ],
        capture_output=True,
        check=True,
        timeout=120,
    )

    manifest = worker.run_ffmpeg(source, tmp_path / "hls")

    assert manifest.name == worker.MANIFEST_NAME
    text = manifest.read_text(encoding="utf-8")
    assert text.startswith("#EXTM3U")
    # VOD playlists are the ones a player can seek in.
    assert "#EXT-X-PLAYLIST-TYPE:VOD" in text
    assert list(manifest.parent.glob("segment_*.ts"))
    assert worker.probe_duration_seconds(source) == 4


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe không có trên máy này")
def test_a_file_that_is_not_a_video_is_reported_not_crashed(tmp_path: Path) -> None:
    source = tmp_path / "khong-phai-video.mp4"
    source.write_bytes(b"day khong phai la video")

    with pytest.raises(TranscodeError) as caught:
        worker.run_ffmpeg(source, tmp_path / "hls")

    assert "ffmpeg" in str(caught.value)
