"""Model package.

Every model module must be imported here: Alembic autogenerate only sees the
tables that have been registered on Base.metadata by import time.
"""

from app.models.banner import BANNER_TITLE_MAX_LENGTH, Banner
from app.models.base import Base
from app.models.category import Category
from app.models.certificate import (
    CERTIFICATE_CODE_ALPHABET,
    CERTIFICATE_CODE_LENGTH,
    Certificate,
)
from app.models.chat import ChatMessage, ChatSession
from app.models.commerce import MAX_CART_ITEMS, Cart, CartItem, Wishlist
from app.models.coupon import (
    COUPON_SCOPES,
    DISCOUNT_TYPES,
    MAX_CODE_LENGTH,
    Coupon,
    CouponCourse,
)
from app.models.course import Course
from app.models.curriculum import CourseSection, Lesson, VideoAsset
from app.models.enrollment import Enrollment
from app.models.gamification import XP_REASON_REF_TYPES, Streak, XpEvent
from app.models.grading import (
    CodeExercise,
    Submission,
    SubmissionResult,
    TestCase,
)
from app.models.notification import (
    NOTIFICATION_COURSE_APPROVED,
    NOTIFICATION_COURSE_REJECTED,
    NOTIFICATION_COURSE_TAKEN_DOWN,
    NOTIFICATION_QA_QUESTION,
    NOTIFICATION_QA_REPLY,
    NOTIFICATION_TYPES,
    Notification,
)
from app.models.order import (
    ORDER_CODE_LENGTH,
    ORDER_STATUSES,
    PAYMENT_PROVIDERS,
    Order,
    OrderItem,
    PaymentEvent,
)
from app.models.progress import LessonProgress
from app.models.qa import (
    QA_BODY_MAX_LENGTH,
    QA_TITLE_MAX_LENGTH,
    QaReply,
    QaThread,
    QaVote,
)
from app.models.quiz import Quiz, QuizAttempt, QuizQuestion
from app.models.rag import EMBEDDING_DIMENSIONS, DocChunk
from app.models.recommendation import CourseEmbedding
from app.models.refresh_token import RefreshToken
from app.models.report import (
    REPORT_DETAILS_MAX_LENGTH,
    REPORT_NOTE_MAX_LENGTH,
    REPORT_PENDING_STATUSES,
    REPORT_REASONS,
    REPORT_STATUSES,
    REPORT_TARGET_TYPES,
    Report,
)
from app.models.review import Review
from app.models.study import Bookmark, Note
from app.models.user import User

__all__ = [
    "Banner",
    "BANNER_TITLE_MAX_LENGTH",
    "Base",
    "Bookmark",
    "Cart",
    "CartItem",
    "Category",
    "Certificate",
    "CERTIFICATE_CODE_ALPHABET",
    "CERTIFICATE_CODE_LENGTH",
    "ChatMessage",
    "ChatSession",
    "CodeExercise",
    "Coupon",
    "COUPON_SCOPES",
    "CouponCourse",
    "Course",
    "CourseEmbedding",
    "CourseSection",
    "DISCOUNT_TYPES",
    "DocChunk",
    "EMBEDDING_DIMENSIONS",
    "Enrollment",
    "Lesson",
    "LessonProgress",
    "MAX_CART_ITEMS",
    "MAX_CODE_LENGTH",
    "Note",
    "Notification",
    "NOTIFICATION_COURSE_APPROVED",
    "NOTIFICATION_COURSE_REJECTED",
    "NOTIFICATION_COURSE_TAKEN_DOWN",
    "NOTIFICATION_QA_QUESTION",
    "NOTIFICATION_QA_REPLY",
    "NOTIFICATION_TYPES",
    "Order",
    "ORDER_CODE_LENGTH",
    "ORDER_STATUSES",
    "OrderItem",
    "PAYMENT_PROVIDERS",
    "PaymentEvent",
    "QA_BODY_MAX_LENGTH",
    "QA_TITLE_MAX_LENGTH",
    "QaReply",
    "QaThread",
    "QaVote",
    "Quiz",
    "QuizAttempt",
    "QuizQuestion",
    "RefreshToken",
    "Report",
    "REPORT_DETAILS_MAX_LENGTH",
    "REPORT_NOTE_MAX_LENGTH",
    "REPORT_PENDING_STATUSES",
    "REPORT_REASONS",
    "REPORT_STATUSES",
    "REPORT_TARGET_TYPES",
    "Review",
    "Streak",
    "Submission",
    "SubmissionResult",
    "TestCase",
    "User",
    "VideoAsset",
    "Wishlist",
    "XP_REASON_REF_TYPES",
    "XpEvent",
]
