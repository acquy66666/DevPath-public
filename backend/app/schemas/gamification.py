"""XP and the streak, as the student reads them."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

XpReason = Literal["lesson_completed", "quiz_passed", "exercise_solved"]


class GamificationSummaryOut(BaseModel):
    xp_total: int
    #: Zero once a whole day has gone by with nothing done. A streak whose
    #: last day was yesterday is still alive: today is not over yet.
    current_streak: int
    longest_streak: int
    #: The last day that counted, as a calendar day in Vietnam.
    last_active_date: date | None
    #: Whether today already counts -- "học một bài để giữ chuỗi" or not.
    active_today: bool


class XpLessonOut(BaseModel):
    id: uuid.UUID
    title: str


class XpCourseOut(BaseModel):
    id: uuid.UUID
    title: str
    slug: str


class XpEventOut(BaseModel):
    id: uuid.UUID
    amount: int
    reason: XpReason
    created_at: datetime
    #: The lesson the award was for -- directly, or the one the quiz or
    #: exercise sits on. Null once it has been deleted: the XP stays.
    lesson: XpLessonOut | None
    course: XpCourseOut | None
