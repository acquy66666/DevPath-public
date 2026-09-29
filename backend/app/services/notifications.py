"""Writing notifications.

A notification is written **inside the transaction of the thing it announces**:
the reply and the "somebody answered you" row commit together or not at all,
so nobody is told about an answer that was rolled back, and no answer goes
unannounced because a second write failed.

Reading them -- the bell, the list, marking as read -- belongs to the in-app
notifications task that follows Q&A in the plan.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NOTIFICATION_TYPES, Notification


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
