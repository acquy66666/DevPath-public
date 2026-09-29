"""Notifications on the wire."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    """One notification.

    `payload` goes out as it was written: which fields it holds depends on
    `type`, and the page is what turns a type and its payload into a sentence
    and a link -- the server does not know the frontend's routes.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int


class MarkAllReadOut(BaseModel):
    #: How many were unread a moment ago.
    marked: int
