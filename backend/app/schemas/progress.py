"""Progress: what the player sends, and what the learning page reads back."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# A lesson longer than this is not a lesson. The cap is here so a bad clock or
# a hand-written request cannot store a position no player will ever reach.
MAX_POSITION_S = 24 * 60 * 60


class ProgressIn(BaseModel):
    """One heartbeat from the player.

    `completed` is optional rather than a boolean defaulting to False: the
    heartbeat leaves it out and must never be able to un-finish a lesson, while
    the button that marks one sends it explicitly.
    """

    last_position_s: int = Field(ge=0, le=MAX_POSITION_S)
    completed: bool | None = None


class LessonProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lesson_id: uuid.UUID
    last_position_s: int
    completed_at: datetime | None


class CourseProgressOut(BaseModel):
    """Everything the learning page needs to draw its table of contents.

    `lesson_count` counts the lessons the course has now, so a course that
    grows a chapter makes everyone's percentage drop -- which is the honest
    answer, not a bug.
    """

    enrollment_id: uuid.UUID
    completed_at: datetime | None
    lesson_count: int
    completed_count: int
    # Where "tiếp tục học" goes: the lesson touched most recently, or the first
    # one when nothing has been watched yet.
    resume_lesson_id: uuid.UUID | None
    lessons: list[LessonProgressOut]
    #: The certificate for this enrolment, once the course has been finished.
    #: It stays after a lesson is unticked -- it was true when it was issued.
    certificate_code: str | None = None
