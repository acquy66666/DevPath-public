"""Pictures inside article lessons.

The same signed-PUT path as avatars and banners: the API signs a URL for a
fresh key, the browser uploads straight to the bucket, and the editor writes
the picture's public address into the Markdown. There is no "complete" step
and no table: the article that names the address is what claims the picture,
and a picture no article names is left to the orphan sweep -- which is what
happens when an instructor deletes the line, closes the tab before saving, or
pastes the same screenshot twice.
"""

import uuid

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.models import User
from app.schemas.lesson_images import LessonImageUploadIn, LessonImageUploadTicket
from app.services import curriculum as curriculum_service
from app.services.rate_limit import RateLimiter
from app.services.storage import ObjectStorage, lesson_image_key
from app.services.upload_limits import enforce_lesson_image_ticket_limit


class LessonNotArticleError(DomainError):
    """Only an article has Markdown to put a picture in."""

    status_code = status.HTTP_409_CONFLICT
    code = "LESSON_NOT_ARTICLE"


async def create_upload_ticket(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    storage: ObjectStorage,
    data: LessonImageUploadIn,
    *,
    limiter: RateLimiter,
) -> LessonImageUploadTicket:
    """Sign a URL the browser may PUT one picture of this lesson to.

    Ownership first, so a stranger hears 403 rather than how many tickets are
    left; the count before signing, so a refused request leaves no URL.
    """
    lesson, _, course = await curriculum_service.lesson_for_management(session, lesson_id, user)
    if lesson.type != "article":
        raise LessonNotArticleError("Chỉ bài đọc mới chèn được ảnh")

    await enforce_lesson_image_ticket_limit(limiter, user.id)

    ttl = get_settings().upload_url_ttl_seconds
    key = lesson_image_key(course.id, data.content_type)
    return LessonImageUploadTicket(
        upload_url=storage.presigned_put_url(
            key, data.content_type, ttl, size_bytes=data.size_bytes
        ),
        storage_key=key,
        public_url=storage.public_url(key),
        expires_in=ttl,
        content_type=data.content_type,
    )
