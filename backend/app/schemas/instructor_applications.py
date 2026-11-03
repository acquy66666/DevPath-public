"""Applying to teach, on the wire: the learner's side and the admin's.

The learner reads their own application back -- status, and the reason when it
was turned down -- but never who decided it. The admin reads the applicant's
email, like every admin screen (`schemas/admin.py`).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.instructor_application import (
    APPLICATION_MOTIVATION_MAX_LENGTH,
    APPLICATION_REASON_MAX_LENGTH,
)
from app.schemas.reports import blank_to_none

ApplicationStatus = Literal["pending", "approved", "rejected"]
ApplicationStatusFilter = Literal["pending", "approved", "rejected", "all"]


class InstructorApplicationCreate(BaseModel):
    motivation: str | None = Field(default=None, max_length=APPLICATION_MOTIVATION_MAX_LENGTH)

    _strip = field_validator("motivation")(blank_to_none)


class InstructorApplicationOut(BaseModel):
    """The applicant's own receipt."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ApplicationStatus
    motivation: str | None
    rejection_reason: str | None
    created_at: datetime
    decided_at: datetime | None


class MyInstructorApplicationOut(BaseModel):
    """`application` is null when the caller has never applied."""

    application: InstructorApplicationOut | None


class ApplicantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    avatar_url: str | None
    role: str
    locked_at: datetime | None
    created_at: datetime


class AdminInstructorApplicationOut(InstructorApplicationOut):
    applicant: ApplicantOut
    #: Courses the applicant is enrolled in -- a hint of how they use the site.
    enrollments_count: int
    #: Applications this person sent before this one, and how they ended.
    earlier_rejections: int


class ApplicationRejectIn(BaseModel):
    """Why an application is turned down -- the learner reads this."""

    reason: str = Field(min_length=1, max_length=APPLICATION_REASON_MAX_LENGTH)

    @field_validator("reason")
    @classmethod
    def not_blank(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Cần ghi lý do để người gửi biết phải bổ sung gì")
        return text
