"""Model package.

Every model module must be imported here: Alembic autogenerate only sees the
tables that have been registered on Base.metadata by import time.
"""

from app.models.base import Base
from app.models.category import Category
from app.models.chat import ChatMessage, ChatSession
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
from app.models.quiz import Quiz, QuizAttempt, QuizQuestion
from app.models.rag import EMBEDDING_DIMENSIONS, DocChunk
from app.models.recommendation import CourseEmbedding
from app.models.refresh_token import RefreshToken
from app.models.review import Review
from app.models.study import Bookmark, Note
from app.models.user import User

__all__ = [
    "Base",
    "Bookmark",
    "Category",
    "ChatMessage",
    "ChatSession",
    "CodeExercise",
    "Course",
    "CourseEmbedding",
    "CourseSection",
    "DocChunk",
    "EMBEDDING_DIMENSIONS",
    "Enrollment",
    "Lesson",
    "LessonProgress",
    "Note",
    "Quiz",
    "QuizAttempt",
    "QuizQuestion",
    "RefreshToken",
    "Review",
    "Submission",
    "SubmissionResult",
    "TestCase",
    "User",
    "VideoAsset",
]
