"""Turning an uploaded file into something a browser can stream.

    original.mp4  --ffmpeg-->  index.m3u8 + segment_000.ts, segment_001.ts, ...

HLS rather than a plain MP4 because the player has to survive a phone on
mobile data: the manifest lets it fetch six seconds at a time and recover from
a stall, and it is what the video player in Phase 2 (hls.js) expects.

The task is a thin wrapper. Everything worth testing lives in `transcode()`,
which takes a session and a storage and knows nothing about Celery.
"""

import asyncio
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models import VideoAsset
from app.services import course_stats
from app.services.storage import ObjectStorage, build_storage, hls_prefix
from app.workers.celery_app import celery_app

# Six seconds per segment: short enough that a player recovers quickly from a
# stall, long enough that a one-hour lecture is 600 files and not 3600.
SEGMENT_SECONDS = 6

# Cap the height at 720p. An instructor's 4K screen recording would otherwise
# be re-encoded at 4K -- unwatchable on mobile data and expensive to store,
# for detail nobody needs to read code on a slide.
MAX_HEIGHT = 720

MANIFEST_NAME = "index.m3u8"

# Spelled out rather than left to `mimetypes`: the table it consults differs
# per operating system, and on Windows `.ts` guesses at TypeScript. A segment
# served as application/octet-stream still plays in hls.js, but Safari's native
# player is fussier and the header costs nothing to get right.
HLS_CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
}

# The instructor reads this; a full traceback would tell them nothing.
ERROR_MESSAGE_MAX_LENGTH = 500

# A long lecture on a small VPS is slow, but a job stuck forever is worse.
TRANSCODE_TIMEOUT_SECONDS = 60 * 60

# What ffmpeg and ffprobe may open while reading an upload. The file is a
# stranger's, and some of ffmpeg's demuxers do what a file tells them: an HLS
# playlist posing as a video is read segment by segment from wherever it
# points, and what it reads becomes the published lecture. ffmpeg 7.1 already
# refuses http there and paths without a media extension, but it still reads
# a local `.ts` (docs/report/assets/phase-6/ffmpeg-hardening.txt). So: local
# files only, and only the two demuxers the accepted uploads need -- mov for
# .mp4/.m4v/.mov, matroska for .mkv/.webm (ALLOWED_VIDEO_EXTENSIONS). These
# are input options and must come before the input they guard.
INPUT_GUARDS = ("-protocol_whitelist", "file", "-format_whitelist", "mov,matroska")


class TranscodeError(RuntimeError):
    """ffmpeg refused the file, or produced nothing usable."""


def probe_duration_seconds(source: Path) -> int | None:
    """Video length, for the curriculum's "3 giờ 20 phút" line.

    None rather than an exception when ffprobe cannot tell: an unknown
    duration is a cosmetic loss, not a reason to fail an upload.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            *INPUT_GUARDS,
            "-print_format", "json",
            "-show_entries", "format=duration",
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return None

    try:
        duration = json.loads(result.stdout)["format"]["duration"]
        return int(float(duration))
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def run_ffmpeg(source: Path, output_dir: Path) -> Path:
    """Re-encode into HLS. Returns the manifest that was written.

    Always re-encodes rather than trying to copy the streams: a file from a
    phone can be HEVC, VP9, or carry audio no browser plays, and finding that
    out at playback time -- on someone else's device -- is the worst place to
    find it out.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = output_dir / MANIFEST_NAME

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            *INPUT_GUARDS,
            "-i", str(source),
            # Escaped comma: ffmpeg splits filter arguments on bare commas.
            "-vf", f"scale=w=-2:h=min({MAX_HEIGHT}\\,ih)",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            # 4:2:0, always. Browsers decode nothing else in hardware, and
            # `-profile:v main` is only defined for 4:2:0 -- feed libx264 a
            # 4:4:4 source without this and it exits -22 with no output file.
            "-pix_fmt", "yuv420p",
            # Baseline-ish profile so older Android players cope.
            "-profile:v", "main",
            "-c:a", "aac",
            "-b:a", "128k",
            # `-hls_time` can only cut on a keyframe, and libx264 emits one
            # every 250 frames by default -- ten seconds at 25fps. Without
            # forcing them the requested six seconds is quietly ignored and
            # segments come out at whatever the GOP happens to be.
            "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_SECONDS})",
            "-hls_time", str(SEGMENT_SECONDS),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(output_dir / "segment_%04d.ts"),
            str(manifest),
        ],
        capture_output=True,
        text=True,
        timeout=TRANSCODE_TIMEOUT_SECONDS,
        check=False,
    )

    if result.returncode != 0:
        # ffmpeg says what went wrong in the last few lines; the rest is a
        # banner listing every codec it was compiled with.
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise TranscodeError(f"ffmpeg thất bại: {tail}")

    if not manifest.exists():
        raise TranscodeError("ffmpeg chạy xong nhưng không sinh ra manifest")

    return manifest


async def transcode(
    session: AsyncSession, storage: ObjectStorage, video_asset_id: uuid.UUID
) -> str:
    """Download, convert, upload, and record how it went.

    Returns the final status. Never raises for a bad video: a failure is a
    row the instructor can read and act on, not a stack trace in a log they
    will never see.
    """
    asset = await session.get(VideoAsset, video_asset_id)
    if asset is None:
        return "missing"

    if asset.status != "processing":
        # Already done, or never handed over. Celery redelivers on worker
        # restart, and doing this twice would republish a finished video.
        return asset.status

    workspace = Path(_make_workspace(video_asset_id))
    try:
        source = workspace / Path(asset.storage_key).name
        storage.download_file(asset.storage_key, str(source))

        manifest = run_ffmpeg(source, workspace / "hls")
        prefix = hls_prefix(asset.id)

        for path in sorted(manifest.parent.iterdir()):
            storage.upload_file(
                str(path),
                f"{prefix}/{path.name}",
                HLS_CONTENT_TYPES.get(path.suffix),
            )

        asset.duration_s = probe_duration_seconds(source)
        asset.hls_manifest_key = f"{prefix}/{MANIFEST_NAME}"
        asset.error_message = None
        asset.status = "ready"
    except Exception as exc:
        # Every failure, on purpose: the row is the error report.
        asset.status = "failed"
        asset.error_message = str(exc)[:ERROR_MESSAGE_MAX_LENGTH]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # In the same transaction as the status: a video that is ready but not yet
    # in the course's total would be a length the catalogue never shows. After
    # a failure too -- cheap, and it never has to be reasoned about.
    course_id = await course_stats.course_of_video(session, asset.id)
    if course_id is not None:
        await course_stats.recount_duration(session, course_id)

    await session.commit()
    return asset.status


def _make_workspace(video_asset_id: uuid.UUID) -> str:
    return tempfile.mkdtemp(prefix=f"transcode-{video_asset_id}-")


@celery_app.task(name="app.workers.video.transcode_video")
def transcode_video(video_asset_id: str) -> str:
    """Celery entry point. Owns the event loop and the database connection."""
    return asyncio.run(_run(uuid.UUID(video_asset_id)))


async def _run(video_asset_id: uuid.UUID) -> str:
    # A fresh engine per task: the worker is sync, so there is no long-lived
    # loop for a pooled connection to belong to.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await transcode(session, build_storage(), video_asset_id)
    finally:
        await engine.dispose()
