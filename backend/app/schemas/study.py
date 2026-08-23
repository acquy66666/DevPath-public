"""Notes and bookmarks on the wire."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.study import NOTE_MAX_LENGTH
from app.schemas.progress import MAX_POSITION_S


def _stripped(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("Nội dung ghi chú không được để trống")
    return text


class NoteCreate(BaseModel):
    """A thought, and the second of the video it is about.

    `timestamp_s` defaults to 0 rather than being required: an article has no
    timeline, and on one of those the field simply means "this lesson".
    """

    content: str = Field(min_length=1, max_length=NOTE_MAX_LENGTH)
    timestamp_s: int = Field(default=0, ge=0, le=MAX_POSITION_S)

    _strip = field_validator("content")(_stripped)


class NoteUpdate(BaseModel):
    """The lesson is absent on purpose: moving a note is writing a new one."""

    content: str = Field(min_length=1, max_length=NOTE_MAX_LENGTH)
    timestamp_s: int | None = Field(default=None, ge=0, le=MAX_POSITION_S)

    _strip = field_validator("content")(_stripped)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lesson_id: uuid.UUID
    timestamp_s: int
    content: str
    created_at: datetime
    updated_at: datetime


class BookmarkedLessonsOut(BaseModel):
    """Which lessons of a course the caller has flagged.

    A list of ids rather than a list of lessons: the page already has the
    curriculum, and this only has to say which rows to draw a flag on.
    """

    lesson_ids: list[uuid.UUID]
