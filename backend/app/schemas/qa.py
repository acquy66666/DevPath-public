"""Questions and answers on the wire."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.qa import QA_BODY_MAX_LENGTH, QA_TITLE_MAX_LENGTH


def _not_blank(value: str | None) -> str | None:
    """Trimmed, and never blank: a question of three spaces is not a question."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise ValueError("Nội dung không được để trống")
    return text


class QaThreadCreate(BaseModel):
    title: str = Field(min_length=1, max_length=QA_TITLE_MAX_LENGTH)
    body: str = Field(min_length=1, max_length=QA_BODY_MAX_LENGTH)

    _strip = field_validator("title", "body")(_not_blank)


class QaThreadUpdate(BaseModel):
    """Only what is sent changes. `resolved` is the "đã giải quyết" switch."""

    title: str | None = Field(default=None, min_length=1, max_length=QA_TITLE_MAX_LENGTH)
    body: str | None = Field(default=None, min_length=1, max_length=QA_BODY_MAX_LENGTH)
    resolved: bool | None = None

    _strip = field_validator("title", "body")(_not_blank)


class QaReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=QA_BODY_MAX_LENGTH)

    _strip = field_validator("body")(_not_blank)


class QaAuthorOut(BaseModel):
    """Who wrote it, as a page shows a person -- no email."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    avatar_url: str | None


class QaLessonRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str


class QaCourseRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str


class QaThreadOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    author: QaAuthorOut
    #: Where the question was asked: the instructor's inbox lists questions
    #: from every lesson of every course, and a link needs both.
    lesson: QaLessonRef
    course: QaCourseRef
    vote_count: int
    #: Whether the caller has voted for it -- the button's pressed state.
    voted: bool
    reply_count: int
    #: The "giảng viên đã trả lời" badge.
    has_instructor_reply: bool
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class QaReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    body: str
    author: QaAuthorOut
    is_instructor_reply: bool
    created_at: datetime
    updated_at: datetime
