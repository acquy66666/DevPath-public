"""Video upload endpoints.

The bytes never pass through here. This module hands out a signed URL, then
takes the instructor's word that the upload finished and puts the file in the
worker's queue -- see `services/storage.py` for why.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.video import VideoAssetOut, VideoUploadRequest, VideoUploadTicket
from app.services import video as video_service
from app.services.storage import ObjectStorage, get_storage
from app.services.tasks import TaskQueue, get_task_queue

router = APIRouter(tags=["video"])

Storage = Annotated[ObjectStorage, Depends(get_storage)]
Queue = Annotated[TaskQueue, Depends(get_task_queue)]


@router.post(
    "/lessons/{lesson_id}/video",
    response_model=VideoUploadTicket,
    status_code=status.HTTP_201_CREATED,
)
async def create_video_upload(
    lesson_id: uuid.UUID,
    payload: VideoUploadRequest,
    current_user: CurrentUser,
    session: DbSession,
    storage: Storage,
) -> VideoUploadTicket:
    """Ask for somewhere to put a video.

    Answers 503 `STORAGE_NOT_CONFIGURED` when no bucket has been set up --
    deliberate, and the same shape as Google sign-in: the rest of the system
    keeps working without object storage, this one endpoint does not.
    """
    return await video_service.create_upload_ticket(
        session, lesson_id, current_user, storage, payload
    )


@router.post("/video-assets/{video_asset_id}/complete", response_model=VideoAssetOut)
async def complete_video_upload(
    video_asset_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    queue: Queue,
) -> VideoAssetOut:
    """The browser finished its PUT. Move to `processing` and queue the transcode."""
    asset = await video_service.mark_uploaded(
        session, video_asset_id, current_user, queue
    )
    return video_service.video_out(asset)


@router.post("/video-assets/{video_asset_id}/retry", response_model=VideoAssetOut)
async def retry_video_transcode(
    video_asset_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    queue: Queue,
) -> VideoAssetOut:
    """Try again on a video that failed. The file is already in the bucket."""
    asset = await video_service.retry_transcode(
        session, video_asset_id, current_user, queue
    )
    return video_service.video_out(asset)


@router.get("/video-assets/{video_asset_id}", response_model=VideoAssetOut)
async def get_video_asset(
    video_asset_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> VideoAssetOut:
    """Where the transcode got to. The upload screen polls this.

    Owner only: students reach the same information through the lesson, which
    already knows who is allowed to see it.
    """
    asset, _ = await video_service.load_for_management(
        session, video_asset_id, current_user
    )
    return video_service.video_out(asset)
