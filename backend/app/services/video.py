"""The upload lifecycle of one lecture video.

    uploading -> processing -> ready
                            \\-> failed

`uploading` is created together with the signed URL and means "a URL exists,
nobody has said the bytes arrived". `processing` starts when the browser
reports the upload finished, and is what the worker picks up. Nothing else
moves an asset between states -- the transitions are the whole point of the
table, so they live here rather than being set from three different places.
"""

import uuid

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.models import Lesson, User, VideoAsset
from app.schemas.video import VideoAssetOut, VideoUploadRequest, VideoUploadTicket
from app.services import curriculum as curriculum_service
from app.services.storage import (
    ObjectStorage,
    asset_prefix,
    delete_quietly,
    original_video_key,
)
from app.services.tasks import TaskQueue


class VideoAssetNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "VIDEO_ASSET_NOT_FOUND"


class LessonNotVideoError(DomainError):
    """Attaching a video to an article would produce something unplayable."""

    status_code = status.HTTP_409_CONFLICT
    code = "LESSON_NOT_VIDEO"


class InvalidVideoStatusError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_VIDEO_STATUS"


def public_media_url(key: str | None) -> str | None:
    """Where a browser reads a finished object from.

    Returns None when no public base URL is configured, rather than raising:
    a missing playback host must not stop a lesson from being read.

    A key that is already an absolute URL is handed back untouched. Only seeded
    demo content arrives that way -- it points at a manifest somebody else is
    hosting, so the sample courses play on a machine with no bucket at all. The
    transcode worker never writes one: every key it produces is relative to the
    bucket, which is what lets the bucket and the CDN host change.
    """
    if key is None:
        return None

    if key.startswith(("http://", "https://")):
        return key

    base = get_settings().r2_public_base_url.rstrip("/")
    return f"{base}/{key}" if base else None


def video_out(asset: VideoAsset) -> VideoAssetOut:
    """The asset as the client sees it: a status, and a URL once there is one."""
    return VideoAssetOut(
        id=asset.id,
        status=asset.status,
        duration_s=asset.duration_s,
        error_message=asset.error_message,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        hls_url=public_media_url(asset.hls_manifest_key),
    )


async def _lesson_for_management(
    session: AsyncSession, lesson_id: uuid.UUID, user: User
) -> Lesson:
    lesson, _, _ = await curriculum_service.lesson_for_management(
        session, lesson_id, user
    )
    return lesson


async def create_upload_ticket(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    storage: ObjectStorage,
    data: VideoUploadRequest,
) -> VideoUploadTicket:
    """Sign a URL the browser can upload one video to, and remember that we did.

    Uploading again replaces whatever was there: the row is dropped and its
    objects are scheduled for deletion. Keeping the old asset around would
    leave a lesson pointing at one video while the bucket paid for two.
    """
    lesson = await _lesson_for_management(session, lesson_id, user)

    if lesson.type != "video":
        raise LessonNotVideoError("Chỉ bài học dạng video mới gắn được video")

    previous = lesson.video_asset
    stale_prefix = asset_prefix(previous.id) if previous is not None else None

    # The id is minted here rather than by `gen_random_uuid()`, because the
    # storage key is built from it and the key has to be known before the row
    # is worth writing.
    asset_id = uuid.uuid4()
    asset = VideoAsset(
        id=asset_id,
        storage_key=original_video_key(asset_id, data.filename),
        status="uploading",
    )
    session.add(asset)

    # Through the relationship, not the raw column: with both set, SQLAlchemy
    # trusts the relationship, and a stale one here would null the foreign key
    # it just wrote.
    lesson.video_asset = asset

    if previous is not None:
        await session.delete(previous)

    await session.commit()
    # Both rows: attaching the asset was an UPDATE on `lessons`, and Postgres
    # fills `updated_at` itself, so that one attribute is left expired and the
    # next reader of this lesson would trip over MissingGreenlet.
    await session.refresh(asset)
    await session.refresh(lesson)

    if stale_prefix is not None:
        # After the commit: the objects should only go once the row is really
        # gone, and a failed delete must not cost the instructor their upload.
        delete_quietly(storage, stale_prefix)

    ttl = get_settings().upload_url_ttl_seconds
    return VideoUploadTicket(
        video_asset_id=asset.id,
        upload_url=storage.presigned_put_url(asset.storage_key, data.content_type, ttl),
        storage_key=asset.storage_key,
        expires_in=ttl,
        content_type=data.content_type,
    )


async def load_for_management(
    session: AsyncSession, video_asset_id: uuid.UUID, user: User
) -> tuple[VideoAsset, Lesson]:
    """An asset the caller may act on, with the lesson that owns it.

    Ownership lives on the course, so it is reached the long way round --
    asset to lesson to section to course -- through the curriculum service,
    which is the one place that knows how to walk it.
    """
    asset = await session.get(VideoAsset, video_asset_id)
    if asset is None:
        raise VideoAssetNotFoundError("Không tìm thấy video")

    lesson = await session.scalar(
        select(Lesson).where(Lesson.video_asset_id == asset.id)
    )
    if lesson is None:
        # An asset nobody points at is not reachable by anyone: no lesson
        # means no course means no owner to compare the caller against.
        raise VideoAssetNotFoundError("Không tìm thấy video")

    await _lesson_for_management(session, lesson.id, user)
    return asset, lesson


async def _start_processing(
    session: AsyncSession, asset: VideoAsset, queue: TaskQueue
) -> VideoAsset:
    asset.status = "processing"
    asset.error_message = None
    await session.commit()
    await session.refresh(asset)

    # After the commit, so the worker cannot read the row before it exists in
    # its final shape -- Celery is quite capable of starting first.
    queue.enqueue_transcode(asset.id)
    return asset


async def mark_uploaded(
    session: AsyncSession,
    video_asset_id: uuid.UUID,
    user: User,
    queue: TaskQueue,
) -> VideoAsset:
    """The browser says the bytes are in the bucket. Hand it to the worker.

    Nothing here checks the object really arrived. A HEAD request would only
    move the same failure earlier: the transcode has to survive a missing or
    corrupt file anyway, and it reports that as `failed` with a message the
    instructor can read.
    """
    asset, _ = await load_for_management(session, video_asset_id, user)

    if asset.status != "uploading":
        raise InvalidVideoStatusError(
            f"Video đang ở trạng thái '{asset.status}', không bắt đầu xử lý lại được"
        )

    return await _start_processing(session, asset, queue)


async def retry_transcode(
    session: AsyncSession,
    video_asset_id: uuid.UUID,
    user: User,
    queue: TaskQueue,
) -> VideoAsset:
    """Run the transcode again on a video that is already in the bucket.

    Worth having because most failures are not the file's fault -- a bucket
    that blinked, a worker killed mid-job -- and the alternative is asking the
    instructor to upload half a gigabyte a second time.
    """
    asset, _ = await load_for_management(session, video_asset_id, user)

    if asset.status != "failed":
        raise InvalidVideoStatusError(
            f"Video đang ở trạng thái '{asset.status}', chỉ video lỗi mới xử lý lại được"
        )

    return await _start_processing(session, asset, queue)
