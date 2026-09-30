"""Reports on the wire: what a learner files, and what they get back."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.report import REPORT_DETAILS_MAX_LENGTH

ReportTargetType = Literal["course", "review", "qa_thread", "qa_reply"]
ReportReason = Literal["spam", "offensive", "copyright", "misleading", "other"]


def blank_to_none(value: str | None) -> str | None:
    """Trimmed; an empty box is "nothing written", not an empty string."""
    if value is None:
        return None
    text = value.strip()
    return text or None


class ReportCreate(BaseModel):
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: ReportReason
    details: str | None = Field(default=None, max_length=REPORT_DETAILS_MAX_LENGTH)

    _strip = field_validator("details")(blank_to_none)

    @model_validator(mode="after")
    def other_needs_words(self) -> "ReportCreate":
        # The table refuses it too (`ck_reports_other_has_details`), but as a
        # 500 at commit; this is the 422 the form can put under the box.
        if self.reason == "other" and self.details is None:
            raise ValueError("Chọn 'Khác' thì cần mô tả vấn đề")
        return self


class ReportOut(BaseModel):
    """The reporter's own receipt. Nothing about what the admin decided."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: ReportReason
    details: str | None
    status: str
    created_at: datetime
