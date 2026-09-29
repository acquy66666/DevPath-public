"""The notification bell and its page.

Everything is about the caller's own notifications: no user id in any path,
so there is nobody else's to ask for.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.notifications import MarkAllReadOut, NotificationOut, UnreadCountOut
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import notifications as notifications_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationOut])
async def list_notifications(
    current_user: CurrentUser,
    session: DbSession,
    unread: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[NotificationOut]:
    """Your notifications, newest first. `unread=true` keeps the unread ones."""
    rows, total = await notifications_service.list_for_user(
        session, current_user, unread_only=unread, page=page, page_size=page_size
    )
    return Page[NotificationOut](
        items=[NotificationOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def get_unread_count(current_user: CurrentUser, session: DbSession) -> UnreadCountOut:
    """The number on the bell -- asked often, so it is its own cheap request."""
    return UnreadCountOut(count=await notifications_service.unread_count(session, current_user))


@router.post("/read-all", response_model=MarkAllReadOut)
async def mark_all_read(current_user: CurrentUser, session: DbSession) -> MarkAllReadOut:
    marked = await notifications_service.mark_all_read(session, current_user)
    return MarkAllReadOut(marked=marked)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Idempotent: reading it again keeps the first time it was read.

    404 `NOTIFICATION_NOT_FOUND` for one that does not exist or is not yours.
    """
    await notifications_service.mark_read(session, notification_id, current_user)
