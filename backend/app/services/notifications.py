"""In-app notifications: writing them, and the bell that reads them.

A notification is written **inside the transaction of the thing it announces**:
the reply and the "somebody answered you" row commit together or not at all,
so nobody is told about an answer that was rolled back, and no answer goes
unannounced because a second write failed.

Reading is always about the caller's own notifications -- there is no id of a
person in any path -- and one that is not theirs is answered 404, like a note:
there is nothing to gain from confirming that somebody else's exists.

**Marking as read is idempotent** and keeps the first `read_at`: the bell and
the page may both mark the same one, and "when did they first see it" is the
only reading of that column worth keeping.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import NOTIFICATION_TYPES, Notification, User


class NotificationNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOTIFICATION_NOT_FOUND"


def add(
    session: AsyncSession, *, user_id: uuid.UUID, type: str, payload: dict[str, Any]
) -> Notification:
    """Stage one notification. The caller's commit is what sends it."""
    if type not in NOTIFICATION_TYPES:
        # The table would refuse it too, but only at commit, and then as an
        # IntegrityError that takes the reply down with it.
        raise ValueError(f"unknown notification type: {type!r}")

    notification = Notification(user_id=user_id, type=type, payload=payload)
    session.add(notification)
    return notification


async def list_for_user(
    session: AsyncSession, user: User, *, unread_only: bool, page: int, page_size: int
) -> tuple[list[Notification], int]:
    """The caller's notifications, newest first."""
    conditions = [Notification.user_id == user.id]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))

    rows = await session.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    total = await session.scalar(select(func.count()).select_from(Notification).where(*conditions))
    return list(rows), total or 0


async def unread_count(session: AsyncSession, user: User) -> int:
    """The number on the bell. Reads the partial index of unread rows only."""
    count = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return count or 0


async def mark_read(session: AsyncSession, notification_id: uuid.UUID, user: User) -> None:
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise NotificationNotFoundError("Không tìm thấy thông báo")

    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await session.commit()


async def mark_all_read(session: AsyncSession, user: User) -> int:
    """Everything unread becomes read. Returns how many that was."""
    result = await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    await session.commit()
    return result.rowcount
