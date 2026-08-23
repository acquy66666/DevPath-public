"""What an enrolment looks like on the way out."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.courses import CourseCardOut


class EnrollmentOut(BaseModel):
    """The fact that this account is taking this course.

    No `user_id`: every endpoint that returns one of these is answering about
    the caller, and a field nobody can vary is a field nobody should read.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    source: str
    completed_at: datetime | None
    created_at: datetime


class EnrolledCourseOut(BaseModel):
    """A row of "Khóa học của tôi".

    The same card the catalogue draws, plus the two dates that only mean
    something once you are enrolled. Progress will join them when
    `lesson_progress` exists; until then a course is either finished or not.
    """

    course: CourseCardOut
    enrolled_at: datetime
    completed_at: datetime | None
