"""Model package.

Every model module must be imported here: Alembic autogenerate only sees the
tables that have been registered on Base.metadata by import time.
"""

from app.models.base import Base
from app.models.category import Category
from app.models.course import Course
from app.models.curriculum import CourseSection, Lesson, VideoAsset
from app.models.enrollment import Enrollment
from app.models.grading import (
    CodeExercise,
    Submission,
    SubmissionResult,
    TestCase,
)
from app.models.progress import LessonProgress
from app.models.rag import EMBEDDING_DIMENSIONS, DocChunk
from app.models.refresh_token import RefreshToken
from app.models.review import Review
from app.models.study import Bookmark, Note
from app.models.user import User

__all__ = [
    "Base",
    "Bookmark",
    "Category",
    "CodeExercise",
    "Course",
    "CourseSection",
    "DocChunk",
    "EMBEDDING_DIMENSIONS",
    "Enrollment",
    "Lesson",
    "LessonProgress",
    "Note",
    "RefreshToken",
    "Review",
    "Submission",
    "SubmissionResult",
    "TestCase",
    "User",
    "VideoAsset",
]
