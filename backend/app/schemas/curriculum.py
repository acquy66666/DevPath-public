"""Sections, lessons, and the two shapes a lesson comes back in.

`LessonSummary` is the table of contents -- what a visitor may see before
paying. `LessonOut` is the lesson itself. Keeping them apart means the public
tree cannot leak the content by someone adding a field to one model.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.video import VideoAssetOut

TITLE_MAX_LENGTH = 200

# What the curriculum builder can create. A `code_exercise` lesson is an empty
# shell until the exercise is attached to it -- statement, limits and test
# cases have their own endpoints, because they are a form of their own and
# because the answer key must never travel through a curriculum schema.
# Quizzes join this list in Phase 4, on the same terms.
BuildableLessonType = Literal["video", "article", "code_exercise"]


def _strip_title(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Tiêu đề không được để trống")
    return stripped


class SectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)

    _strip = field_validator("title")(_strip_title)


class SectionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)

    _strip = field_validator("title")(_strip_title)


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    type: BuildableLessonType
    is_preview: bool = False
    article_content: str | None = None

    _strip = field_validator("title")(_strip_title)


class LessonUpdate(BaseModel):
    """Everything optional; `position` and `section_id` are not here.

    Moving a lesson is what the reorder endpoint is for -- it is the only place
    that can renumber the rows left behind.
    """

    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    is_preview: bool | None = None
    article_content: str | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        return None if value is None else _strip_title(value)


class LessonSummary(BaseModel):
    """A row in the table of contents. Carries no content on purpose."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    type: str
    position: int
    is_preview: bool


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section_id: uuid.UUID
    title: str
    type: str
    position: int
    is_preview: bool
    video_asset_id: uuid.UUID | None
    article_content: str | None
    created_at: datetime
    updated_at: datetime

    # Filled in by the router. Default None so a lesson still validates when
    # nobody asked about its video.
    video: VideoAssetOut | None = None


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    position: int


class SectionWithLessons(SectionOut):
    lessons: list[LessonSummary]


class CurriculumOut(BaseModel):
    sections: list[SectionWithLessons]


class SectionOrder(BaseModel):
    """Every section of the course, in the order they should end up.

    The whole arrangement rather than a move instruction: the client already
    knows what the list looks like after a drag, and sending it whole means no
    sequence of partial updates can leave the order half-applied.
    """

    section_ids: list[uuid.UUID] = Field(min_length=1)


class LessonOrder(BaseModel):
    """The complete contents of one section, in order.

    A lesson listed here that currently sits in another section of the same
    course is moved in -- which is exactly what dropping it there means.
    """

    lesson_ids: list[uuid.UUID]
