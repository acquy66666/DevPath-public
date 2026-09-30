"""The admin screens on the wire: the review queue, accounts, reports.

Unlike every public schema, a person here carries their **email**: the admin
has to be able to tell two accounts called "Nguyễn Văn A" apart, and to reach
the one they are about to lock.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.report import REPORT_NOTE_MAX_LENGTH
from app.schemas.categories import CategoryOut
from app.schemas.reports import ReportReason, ReportTargetType, blank_to_none

REASON_MAX_LENGTH = 1000


class AdminPersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    avatar_url: str | None
    role: str
    locked_at: datetime | None


# --- Courses ---------------------------------------------------------------


class AdminCourseOut(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    subtitle: str | None
    description: str | None
    thumbnail_url: str | None
    price: Decimal
    level: str
    status: str
    rejection_reason: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    duration_total_s: int
    lessons_count: int
    students_count: int
    instructor: AdminPersonOut
    category: CategoryOut


class CourseDecisionIn(BaseModel):
    """Why a course is sent back or taken down -- the instructor reads this."""

    reason: str = Field(min_length=1, max_length=REASON_MAX_LENGTH)

    @field_validator("reason")
    @classmethod
    def not_blank(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Cần ghi lý do để giảng viên biết phải sửa gì")
        return text


# --- Users -----------------------------------------------------------------


class AdminUserOut(AdminPersonOut):
    oauth_provider: str | None
    has_password: bool
    created_at: datetime
    last_login_at: datetime | None
    courses_count: int
    enrollments_count: int


# --- Reports ---------------------------------------------------------------


class ReportCourseRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    status: str


class ReportTargetOut(BaseModel):
    """The reported thing as it is now. `exists=False`: it has been deleted.

    Ids rather than URLs, like notifications: the page knows its own routes.
    """

    exists: bool
    title: str | None
    excerpt: str | None
    rating: int | None
    author: AdminPersonOut | None
    course: ReportCourseRef | None
    lesson_id: uuid.UUID | None
    thread_id: uuid.UUID | None


class AdminReportOut(BaseModel):
    id: uuid.UUID
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: ReportReason
    details: str | None
    status: str
    created_at: datetime
    reporter: AdminPersonOut
    target: ReportTargetOut
    pending_on_target: int
    resolved_at: datetime | None
    resolved_by: AdminPersonOut | None
    resolution_note: str | None
    content_removed: bool


class ReportResolveIn(BaseModel):
    note: str | None = Field(default=None, max_length=REPORT_NOTE_MAX_LENGTH)
    remove_content: bool = False

    _strip = field_validator("note")(blank_to_none)


class ReportDismissIn(BaseModel):
    note: str | None = Field(default=None, max_length=REPORT_NOTE_MAX_LENGTH)

    _strip = field_validator("note")(blank_to_none)


# --- The badges on the admin's tabs -----------------------------------------


class AdminSummaryOut(BaseModel):
    pending_courses: int
    pending_reports: int
    locked_users: int


AdminCourseStatus = Literal["pending_review", "published", "rejected", "draft", "all"]
