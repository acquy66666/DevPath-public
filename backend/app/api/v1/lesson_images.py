"""Pictures inside article lessons. The bytes never pass through here."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.lesson_images import LessonImageUploadIn, LessonImageUploadTicket
from app.services import lesson_images as lesson_images_service
from app.services.rate_limit import RateLimiter, get_rate_limiter
from app.services.storage import ObjectStorage, get_storage

router = APIRouter(tags=["lesson-images"])

Storage = Annotated[ObjectStorage, Depends(get_storage)]
RateLimit = Annotated[RateLimiter, Depends(get_rate_limiter)]


@router.post(
    "/lessons/{lesson_id}/images",
    response_model=LessonImageUploadTicket,
    status_code=status.HTTP_201_CREATED,
)
async def create_lesson_image_upload(
    lesson_id: uuid.UUID,
    payload: LessonImageUploadIn,
    current_user: CurrentUser,
    session: DbSession,
    storage: Storage,
    limiter: RateLimit,
) -> LessonImageUploadTicket:
    """Ask for somewhere to put one picture of an article lesson.

    The lesson's instructor (or an admin) only; 409 LESSON_NOT_ARTICLE for any
    other lesson type; 503 STORAGE_NOT_CONFIGURED without a bucket; 429
    UPLOAD_RATE_LIMITED after `lesson_image_upload_tickets_per_user` in a day.
    """
    return await lesson_images_service.create_upload_ticket(
        session, lesson_id, current_user, storage, payload, limiter=limiter
    )
