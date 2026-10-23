"""Every route, asked by somebody it does not belong to.

The feature tests each prove their own resource is guarded. This file proves
the same thing for all of them at once, from the outside, so that "authorization
on every endpoint" is a statement the suite checks rather than one a reviewer
has to believe.

Three rules hold the file together:

* **Every route is classified.** `RULES` names every method + path the app
  serves. A new route that is not in it fails `test_every_route_is_classified`,
  so the question "who may call this?" is answered when the route is written,
  not when somebody audits it later.
* **A refusal must come from the rule, not from a broken request.** Each owned
  route is also called by its rightful owner, who must get through. Without
  that, a typo in the world below would turn every probe into a 404 and every
  test green.
* **Outsiders are chosen to be the hard case.** The enrolled classmate, not
  just the anonymous visitor, asks for a learner's notes; the enrolled learner,
  not just a stranger, tries to edit the course. A guard that only checks
  "enrolled" passes the easy case and fails these.

Actors:

    teacher    instructor who owns the course
    rival      another instructor -- right role, wrong course
    learner    enrolled student who owns the private rows below
    classmate  another student enrolled in the same course
    stranger   a student who is not enrolled
    admin      only used for /admin/*
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models import (
    Bookmark,
    Category,
    ChatSession,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Note,
    Notification,
    Order,
    OrderItem,
    QaReply,
    QaThread,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Review,
    Submission,
    TestCase,
    User,
    VideoAsset,
)
from app.services import grading as grading_service
from app.services.llm import (
    LLMNotConfiguredError,
    get_chat_model_factory,
    get_embedder_factory,
    get_quiz_model_factory,
)
from app.services.recommendations import get_recommendation_cache
from app.services.storage import get_storage, get_storage_factory
from app.services.tasks import get_task_queue
from tests.api.fakes import FakeQueue, FakeStorage, MemoryRecommendationCache

API = "/api/v1"

#: The answer to the hidden test case. Never in a response anybody but the
#: teacher reads.
HIDDEN_OUTPUT = "đáp-án-ẩn-7f3a"

#: Hashed once: six bcrypt rounds per world, times two hundred worlds, is
#: minutes of hashing for passwords nobody here signs in with.
PASSWORD_HASH = hash_password("mật-khẩu-đủ-dài")

#: What an owned route answers an outsider with. 404 where admitting the row
#: exists would itself be a leak, 403 where the caller can already see it.
REFUSED = frozenset({403, 404})

#: What the rightful owner must *not* get. Anything else -- 2xx, a 409 about
#: the state of the row, a 503 for an unconfigured provider -- means the
#: request got past authorization, which is all this file asks.
DENIED = {401, 403, 404, 422}


# --- the world ----------------------------------------------------------------


@dataclass
class World:
    users: dict[str, User]
    ids: dict[str, str] = field(default_factory=dict)

    def headers(self, actor: str) -> dict[str, str]:
        user = self.users[actor]
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


async def build_world(session: AsyncSession) -> World:
    """One published course with one lesson of each kind, and one of every
    private row a learner can own inside it."""
    tag = uuid.uuid4().hex[:8]
    now = datetime.now(UTC)

    def person(role: str, name: str) -> User:
        return User(
            email=f"{name}-{tag}@example.com",
            full_name=name.title(),
            password_hash=PASSWORD_HASH,
            role=role,
        )

    users = {
        "teacher": person("instructor", "teacher"),
        "rival": person("instructor", "rival"),
        "learner": person("student", "learner"),
        "classmate": person("student", "classmate"),
        "stranger": person("student", "stranger"),
        "admin": person("admin", "admin"),
    }
    session.add_all(users.values())
    await session.flush()

    category = Category(name=f"Ma trận {tag}", slug=f"ma-tran-{tag}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=users["teacher"].id,
        category_id=category.id,
        title="Khóa học ma trận quyền",
        slug=f"ma-tran-quyen-{tag}",
        price=Decimal("0"),
        status="published",
        published_at=now,
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    asset = VideoAsset(
        storage_key=f"videos/{tag}/source.mp4",
        status="ready",
        hls_manifest_key=f"videos/{tag}/hls/master.m3u8",
        transcript_key=f"videos/{tag}/transcript.txt",
        duration_s=60,
    )
    session.add_all([section, asset])
    await session.flush()

    video = Lesson(
        section_id=section.id,
        title="Video",
        type="video",
        position=0,
        video_asset_id=asset.id,
    )
    article = Lesson(
        section_id=section.id,
        title="Bài đọc",
        type="article",
        position=1,
        article_content="Vòng lặp for duyệt qua từng phần tử.",
    )
    code = Lesson(section_id=section.id, title="Bài code", type="code_exercise", position=2)
    quiz_lesson = Lesson(section_id=section.id, title="Bài quiz", type="quiz", position=3)
    session.add_all([video, article, code, quiz_lesson])
    await session.flush()

    exercise = CodeExercise(lesson_id=code.id, statement_md="In ra số 1.")
    quiz = Quiz(lesson_id=quiz_lesson.id, is_published=True)
    session.add_all([exercise, quiz])
    await session.flush()

    sample = TestCase(exercise_id=exercise.id, expected_output="1", is_hidden=False, position=0)
    hidden = TestCase(
        exercise_id=exercise.id, expected_output=HIDDEN_OUTPUT, is_hidden=True, position=1
    )
    question = QuizQuestion(
        quiz_id=quiz.id,
        question="1 + 1 bằng mấy?",
        options=["1", "2"],
        correct_index=1,
        position=0,
    )
    session.add_all([sample, hidden, question])
    for student in ("learner", "classmate"):
        session.add(Enrollment(user_id=users[student].id, course_id=course.id, source="free"))
    await session.flush()

    learner = users["learner"].id
    note = Note(user_id=learner, lesson_id=article.id, content="ghi chú riêng")
    bookmark = Bookmark(user_id=learner, lesson_id=article.id)
    chat = ChatSession(user_id=learner, course_id=course.id)
    submission = Submission(
        user_id=learner,
        exercise_id=exercise.id,
        code="print(1)",
        language="python",
    )
    attempt = QuizAttempt(quiz_id=quiz.id, user_id=learner)
    thread = QaThread(
        lesson_id=article.id,
        user_id=learner,
        title="Vì sao range dừng ở 4?",
        body="Em tưởng range(5) in cả số 5.",
    )
    review = Review(course_id=course.id, user_id=learner, rating=5)
    order = Order(
        user_id=learner,
        code=f"DP261001{tag[:6].upper()}",
        subtotal=Decimal("0"),
        total=Decimal("0"),
    )
    notification = Notification(user_id=learner, type="qa_reply", payload={})
    session.add_all(
        [note, bookmark, chat, submission, attempt, thread, review, order, notification]
    )
    await session.flush()

    reply = QaReply(thread_id=thread.id, user_id=learner, body="Em hiểu rồi ạ.")
    session.add_all(
        [reply, OrderItem(order_id=order.id, course_id=course.id, unit_price=Decimal("0"))]
    )
    await session.flush()

    world = World(users=users)
    world.ids = {
        "course_id": str(course.id),
        "category_id": str(category.id),
        "slug": course.slug,
        "section_id": str(section.id),
        "video_lesson": str(video.id),
        "article_lesson": str(article.id),
        "code_lesson": str(code.id),
        "quiz_lesson": str(quiz_lesson.id),
        "video_asset_id": str(asset.id),
        "exercise_id": str(exercise.id),
        "sample_case": str(sample.id),
        "test_case_id": str(hidden.id),
        "quiz_id": str(quiz.id),
        "question_id": str(question.id),
        "note_id": str(note.id),
        "bookmark": str(bookmark.id),
        "session_id": str(chat.id),
        "submission_id": str(submission.id),
        "attempt_id": str(attempt.id),
        "thread_id": str(thread.id),
        "reply_id": str(reply.id),
        "review": str(review.id),
        "code": order.code,
        "notification_id": str(notification.id),
        "hidden_output": HIDDEN_OUTPUT,
    }
    return world


#: Rows only the learner should ever read back. A self-scoped route called by
#: somebody else must not mention any of them.
LEARNER_PRIVATE = (
    "note_id",
    "bookmark",
    "session_id",
    "submission_id",
    "attempt_id",
    "code",
    "notification_id",
)


# --- the rules ----------------------------------------------------------------


@dataclass(frozen=True)
class Public:
    """No sign-in needed, by design. `why` is the design."""

    why: str


@dataclass(frozen=True)
class Admin:
    """`require_role("admin")`: a student and an instructor are both refused."""


@dataclass(frozen=True)
class Owned:
    """Belongs to `owner`; every one of `outsiders` is refused."""

    owner: str
    outsiders: tuple[str, ...]
    body: dict | None = None
    #: Path parameter -> key in `World.ids`, where the name alone is ambiguous.
    params: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    #: What counts as "refused". Wider only where a rule says *why* in a
    #: status of its own -- the teacher reviewing their own course is a 409.
    refused: frozenset[int] = frozenset(REFUSED)


@dataclass(frozen=True)
class Scoped:
    """Answers about the caller only. `actor` may call it, and the answer
    must not mention any of `secrets`."""

    actor: str
    secrets: tuple[str, ...] = LEARNER_PRIVATE
    body: dict | None = None
    params: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Open:
    """Any signed-in user may do this to a public resource. `why` says why."""

    actor: str
    why: str
    body: dict | None = None


Rule = Public | Admin | Owned | Scoped | Open

AUTHORS = ("rival", "learner")  # right role or right course, never both
LEARNER_EYES_ONLY = ("classmate", "teacher")
NOT_IN_CLASS = ("stranger", "rival")

VIDEO = {"lesson_id": "video_lesson"}
CODE = {"lesson_id": "code_lesson"}
QUIZ = {"lesson_id": "quiz_lesson"}

RULES: dict[str, Rule] = {
    # Public by design ---------------------------------------------------------
    "GET /health": Public("liveness probe"),
    "GET /health/ready": Public("readiness probe for deploy.sh and uptime checks"),
    "POST /auth/register": Public("the way in"),
    "POST /auth/login": Public("the way in"),
    "POST /auth/refresh": Public("the cookie is the credential"),
    "POST /auth/logout": Public("must work after the access token expired"),
    "GET /auth/google/authorize": Public("the way in"),
    "GET /auth/google/callback": Public("state cookie + code exchange are the check"),
    "GET /payments/vnpay/ipn": Public("server-to-server; the HMAC signature is the check"),
    "GET /banners": Public("home page carousel"),
    "GET /categories": Public("catalogue"),
    "GET /courses": Public("catalogue; published courses only"),
    "GET /courses/by-slug/{slug}": Public("published course page; drafts 404 (test_course_detail)"),
    "GET /courses/{course_id}": Public("published course page; drafts 404 (test_course_detail)"),
    "GET /courses/{course_id}/curriculum": Public("outline only, no lesson bodies"),
    "GET /courses/{course_id}/reviews": Public("reviews are public"),
    "GET /courses/{course_id}/similar": Public("catalogue"),
    "GET /certificates/{code}": Public("verification page behind the QR code"),
    "GET /certificates/{code}/pdf": Public("verification page behind the QR code"),
    "WS /submissions/{submission_id}/events": Public(
        "authenticates in the handshake itself (test_grading: a stranger gets no snapshot)"
    ),
    # Course authoring: the teacher, and not the enrolled learner --------------
    "PATCH /courses/{course_id}": Owned("teacher", AUTHORS, body={"subtitle": "Mới"}),
    "DELETE /courses/{course_id}": Owned("teacher", AUTHORS),
    "POST /courses/{course_id}/submit": Owned("teacher", AUTHORS),
    "POST /courses/{course_id}/unpublish": Owned("teacher", AUTHORS),
    "POST /courses/{course_id}/sections": Owned("teacher", AUTHORS, body={"title": "Chương 2"}),
    "PUT /courses/{course_id}/sections/order": Owned(
        "teacher", AUTHORS, body={"section_ids": ["{section_id}"]}
    ),
    "PATCH /sections/{section_id}": Owned("teacher", AUTHORS, body={"title": "Chương một"}),
    "DELETE /sections/{section_id}": Owned("teacher", AUTHORS),
    "POST /sections/{section_id}/lessons": Owned(
        "teacher", AUTHORS, body={"title": "Bài mới", "type": "article"}
    ),
    "PUT /sections/{section_id}/lessons/order": Owned(
        "teacher",
        AUTHORS,
        body={
            "lesson_ids": ["{video_lesson}", "{article_lesson}", "{code_lesson}", "{quiz_lesson}"]
        },
    ),
    "PATCH /lessons/{lesson_id}": Owned(
        "teacher", AUTHORS, body={"title": "Bài đọc mới"}, params={"lesson_id": "article_lesson"}
    ),
    "DELETE /lessons/{lesson_id}": Owned(
        "teacher", AUTHORS, params={"lesson_id": "article_lesson"}
    ),
    "POST /lessons/{lesson_id}/video": Owned(
        "teacher",
        AUTHORS,
        params=VIDEO,
        body={"filename": "bai.mp4", "content_type": "video/mp4", "size_bytes": 1000},
    ),
    "POST /lessons/{lesson_id}/images": Owned(
        "teacher",
        AUTHORS,
        params={"lesson_id": "article_lesson"},
        body={"content_type": "image/png", "size_bytes": 1000},
    ),
    "GET /video-assets/{video_asset_id}": Owned("teacher", AUTHORS),
    "POST /video-assets/{video_asset_id}/complete": Owned("teacher", AUTHORS),
    "POST /video-assets/{video_asset_id}/retry": Owned("teacher", AUTHORS),
    "PUT /lessons/{lesson_id}/transcript": Owned(
        "teacher",
        AUTHORS,
        params=VIDEO,
        body={"filename": "bai.txt", "content": "Xin chào các bạn."},
    ),
    "DELETE /lessons/{lesson_id}/transcript": Owned("teacher", AUTHORS, params=VIDEO),
    "POST /lessons/{lesson_id}/code-exercise": Owned(
        "teacher", AUTHORS, params=CODE, body={"statement_md": "Đề mới"}
    ),
    "PATCH /code-exercises/{exercise_id}": Owned("teacher", AUTHORS, body={"statement_md": "Đề"}),
    "DELETE /code-exercises/{exercise_id}": Owned("teacher", AUTHORS),
    "POST /code-exercises/{exercise_id}/test-cases": Owned(
        "teacher", AUTHORS, body={"expected_output": "2"}
    ),
    "PUT /code-exercises/{exercise_id}/test-cases/order": Owned(
        "teacher", AUTHORS, body={"test_case_ids": ["{sample_case}", "{test_case_id}"]}
    ),
    "PATCH /test-cases/{test_case_id}": Owned("teacher", AUTHORS, body={"expected_output": "3"}),
    "DELETE /test-cases/{test_case_id}": Owned("teacher", AUTHORS),
    "POST /lessons/{lesson_id}/quiz": Owned("teacher", AUTHORS, params=QUIZ, body={}),
    "PATCH /quizzes/{quiz_id}": Owned("teacher", AUTHORS, body={"pass_score": 60}),
    "DELETE /quizzes/{quiz_id}": Owned("teacher", AUTHORS),
    # The answer key. The enrolled learner is the one who must not read it.
    "GET /quizzes/{quiz_id}/questions": Owned("teacher", AUTHORS),
    "POST /quizzes/{quiz_id}/questions": Owned(
        "teacher", AUTHORS, body={"question": "2 + 2?", "options": ["3", "4"], "correct_index": 1}
    ),
    "POST /quizzes/{quiz_id}/generate": Owned(
        "teacher", AUTHORS, body={"source_lesson_id": "{article_lesson}"}
    ),
    "PATCH /quiz-questions/{question_id}": Owned("teacher", AUTHORS, body={"question": "1 + 1?"}),
    "DELETE /quiz-questions/{question_id}": Owned("teacher", AUTHORS),
    "POST /quiz-questions/{question_id}/approve": Owned("teacher", AUTHORS),
    # Lesson content: the class and its teacher ---------------------------------
    "GET /lessons/{lesson_id}": Owned(
        "learner", NOT_IN_CLASS, params={"lesson_id": "article_lesson"}
    ),
    "GET /lessons/{lesson_id}/code-exercise": Owned("learner", NOT_IN_CLASS, params=CODE),
    "GET /lessons/{lesson_id}/quiz": Owned("learner", NOT_IN_CLASS, params=QUIZ),
    "PUT /lessons/{lesson_id}/progress": Owned(
        "learner",
        NOT_IN_CLASS,
        params={"lesson_id": "article_lesson"},
        body={"last_position_s": 0},
    ),
    "POST /lessons/{lesson_id}/notes": Owned(
        "learner",
        NOT_IN_CLASS,
        params={"lesson_id": "article_lesson"},
        body={"content": "ghi chú"},
    ),
    "PUT /lessons/{lesson_id}/bookmark": Owned(
        "classmate", NOT_IN_CLASS, params={"lesson_id": "article_lesson"}
    ),
    "POST /code-exercises/{exercise_id}/submissions": Owned(
        "learner", NOT_IN_CLASS, body={"code": "print(1)"}
    ),
    "POST /code-exercises/{exercise_id}/trial-runs": Owned(
        "learner", NOT_IN_CLASS, body={"code": "print(1)"}
    ),
    "POST /quizzes/{quiz_id}/attempts": Owned("learner", NOT_IN_CLASS),
    "GET /lessons/{lesson_id}/qa-threads": Owned(
        "classmate", NOT_IN_CLASS, params={"lesson_id": "article_lesson"}
    ),
    "POST /lessons/{lesson_id}/qa-threads": Owned(
        "classmate",
        NOT_IN_CLASS,
        params={"lesson_id": "article_lesson"},
        body={"title": "Câu hỏi", "body": "Nội dung"},
    ),
    "GET /qa-threads/{thread_id}": Owned("classmate", NOT_IN_CLASS),
    "GET /qa-threads/{thread_id}/replies": Owned("classmate", NOT_IN_CLASS),
    "POST /qa-threads/{thread_id}/replies": Owned("classmate", NOT_IN_CLASS, body={"body": "Vì…"}),
    "PUT /qa-threads/{thread_id}/vote": Owned("classmate", NOT_IN_CLASS),
    # The teacher may tidy the board; a classmate may not.
    "PATCH /qa-threads/{thread_id}": Owned(
        "learner", ("classmate", *NOT_IN_CLASS), body={"title": "Sửa tiêu đề"}
    ),
    "DELETE /qa-threads/{thread_id}": Owned("learner", ("classmate", *NOT_IN_CLASS)),
    "DELETE /qa-replies/{reply_id}": Owned("learner", ("classmate", *NOT_IN_CLASS)),
    # The assistant answers the class; its own teacher is not a student of it.
    "POST /courses/{course_id}/chat-sessions": Owned("learner", (*NOT_IN_CLASS, "teacher")),
    "PUT /courses/{course_id}/reviews/me": Owned(
        "learner",
        (*NOT_IN_CLASS, "teacher"),
        body={"rating": 4},
        refused=frozenset({*REFUSED, 409}),  # CANNOT_REVIEW_OWN_COURSE
    ),
    # One learner's rows: nobody else, the teacher included ----------------------
    "GET /chat-sessions/{session_id}/messages": Owned("learner", LEARNER_EYES_ONLY),
    "POST /chat-sessions/{session_id}/messages": Owned(
        "learner", LEARNER_EYES_ONLY, body={"content": "Vòng lặp for là gì?"}
    ),
    "DELETE /chat-sessions/{session_id}": Owned("learner", LEARNER_EYES_ONLY),
    "GET /quiz-attempts/{attempt_id}": Owned("learner", LEARNER_EYES_ONLY),
    "POST /quiz-attempts/{attempt_id}/submit": Owned(
        "learner", LEARNER_EYES_ONLY, body={"answers": [1]}
    ),
    "PATCH /notes/{note_id}": Owned("learner", LEARNER_EYES_ONLY, body={"content": "sửa"}),
    "DELETE /notes/{note_id}": Owned("learner", LEARNER_EYES_ONLY),
    "GET /orders/{code}": Owned("learner", LEARNER_EYES_ONLY),
    "POST /orders/{code}/payment-url": Owned("learner", LEARNER_EYES_ONLY),
    "POST /notifications/{notification_id}/read": Owned("learner", LEARNER_EYES_ONLY),
    # The teacher may watch a submission to their own exercise; nobody else.
    "GET /submissions/{submission_id}": Owned("learner", ("classmate", "stranger", "rival")),
    # About the caller only -------------------------------------------------------
    "GET /auth/me": Scoped("classmate"),
    "PATCH /users/me": Scoped("classmate", body={"full_name": "Bạn Cùng Lớp"}),
    "POST /users/me/password": Scoped(
        "classmate",
        body={"current_password": "sai-mật-khẩu-rồi", "new_password": "mật-khẩu-mới-dài"},
    ),
    "POST /users/me/avatar": Scoped(
        "classmate", body={"filename": "a.png", "content_type": "image/png", "size_bytes": 100}
    ),
    # The key is checked against the caller's own folder: aiming it at the
    # learner's folder is refused (test_avatar has the rest).
    "POST /users/me/avatar/complete": Scoped(
        "classmate", body={"storage_key": "avatars/{learner}/x.png"}
    ),
    "POST /users/me/instructor": Scoped("classmate"),
    "GET /users/me/gamification": Scoped("classmate"),
    "GET /users/me/xp-events": Scoped("classmate"),
    "GET /enrollments/me": Scoped("classmate"),
    "GET /notifications": Scoped("classmate"),
    "GET /notifications/unread-count": Scoped("classmate"),
    "POST /notifications/read-all": Scoped("classmate"),
    "GET /cart": Scoped("classmate"),
    "DELETE /cart": Scoped("classmate"),
    "POST /cart/coupon": Scoped("classmate", body={"code": "KHONGCO"}),
    "POST /orders": Scoped("classmate", body={}),
    "GET /wishlist": Scoped("classmate"),
    "GET /wishlist/course-ids": Scoped("classmate"),
    "GET /recommendations": Scoped("classmate"),
    "GET /courses/{course_id}/enrollment": Scoped("classmate"),
    "GET /courses/{course_id}/progress": Scoped("classmate"),
    "GET /courses/{course_id}/bookmarks": Scoped("classmate"),
    "GET /courses/{course_id}/chat-sessions": Scoped("classmate"),
    "GET /courses/{course_id}/reviews/me": Scoped("classmate"),
    "DELETE /courses/{course_id}/reviews/me": Scoped("classmate"),
    "GET /lessons/{lesson_id}/notes": Scoped("classmate", params={"lesson_id": "article_lesson"}),
    "DELETE /lessons/{lesson_id}/bookmark": Scoped(
        "classmate", params={"lesson_id": "article_lesson"}
    ),
    "GET /code-exercises/{exercise_id}/submissions": Scoped("classmate"),
    "GET /quizzes/{quiz_id}/attempts": Scoped("classmate"),
    "DELETE /qa-threads/{thread_id}/vote": Scoped("classmate"),
    # Samples filled in, hidden cases present but empty.
    "GET /code-exercises/{exercise_id}/test-cases": Scoped("learner", secrets=("hidden_output",)),
    # Another instructor's dashboards never include this course.
    "GET /courses/me": Scoped("rival", secrets=("course_id",)),
    "GET /instructor/stats/overview": Scoped("rival", secrets=("course_id",)),
    "GET /instructor/stats/courses": Scoped("rival", secrets=("course_id",)),
    "GET /instructor/stats/insights": Scoped("rival", secrets=("course_id",)),
    "GET /instructor/stats/export.xlsx": Scoped("rival", secrets=("course_id",)),
    "GET /instructor/tier": Scoped("rival", secrets=("course_id",)),
    # One course, lesson by lesson: its own instructor only (learner: wrong role,
    # rival: not their course -> 404).
    "GET /instructor/stats/courses/{course_id}/lessons": Owned("teacher", AUTHORS),
    "GET /instructor/stats/courses/{course_id}/lessons/export.xlsx": Owned("teacher", AUTHORS),
    "GET /instructor/qa-threads": Scoped(
        "rival", secrets=("thread_id",), query={"course_id": "{course_id}"}
    ),
    # Any signed-in user, on a public resource ------------------------------------
    "POST /courses": Open(
        "rival",
        "an instructor creates their own course",
        body={"title": "Khóa mới", "category_id": "{category_id}"},
    ),
    "POST /courses/{course_id}/enroll": Open("stranger", "a free published course is free to join"),
    "PUT /cart/courses/{course_id}": Open(
        "stranger", "anyone may put a public course in their cart"
    ),
    "DELETE /cart/courses/{course_id}": Open("stranger", "own cart"),
    "PUT /wishlist/courses/{course_id}": Open("stranger", "anyone may wish for a public course"),
    "DELETE /wishlist/courses/{course_id}": Open("stranger", "own wishlist"),
    "GET /courses/{course_id}/next": Open("stranger", "public neighbours less the caller's own"),
    "GET /leaderboard": Open("stranger", "the ranking is shown to every learner"),
    "POST /reports": Open(
        "classmate",
        "anyone who can see a thing may report it",
        body={"target_type": "course", "target_id": "{course_id}", "reason": "spam"},
    ),
}


def app_routes(app: FastAPI) -> dict[str, APIRoute | APIWebSocketRoute]:
    """`METHOD /path` -> route, for every route the app serves under /api/v1."""

    def walk(routes):
        for route in routes:
            if isinstance(route, APIRoute | APIWebSocketRoute):
                yield route
            elif hasattr(route, "original_router"):
                yield from walk(route.original_router.routes)

    found = {}
    for route in walk(app.routes):
        path = route.path.removeprefix(API)
        methods = getattr(route, "methods", None) or {"WS"}
        for method in methods:
            found[f"{method} {path}"] = route
    return found


def is_admin(key: str) -> bool:
    return key.split(" ", 1)[1].startswith("/admin/")


def rule_for(key: str) -> Rule:
    return Admin() if is_admin(key) else RULES[key]


# --- plumbing -----------------------------------------------------------------


@pytest.fixture
async def world(db_session: AsyncSession) -> World:
    return await build_world(db_session)


@pytest.fixture(autouse=True)
def nothing_leaves_the_process(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Storage, Celery, Gemini and the grading queue all stand in.

    The owner's half of every probe reaches the real handler, and some of the
    handlers would otherwise sign URLs, queue jobs or call a model.
    """
    storage = FakeStorage()

    def no_key():
        raise LLMNotConfiguredError("Chưa cấu hình GEMINI_API_KEY")

    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_storage_factory] = lambda: lambda: storage
    app.dependency_overrides[get_task_queue] = FakeQueue
    app.dependency_overrides[get_chat_model_factory] = lambda: no_key
    app.dependency_overrides[get_embedder_factory] = lambda: no_key
    app.dependency_overrides[get_quiz_model_factory] = lambda: no_key
    app.dependency_overrides[get_recommendation_cache] = MemoryRecommendationCache
    monkeypatch.setattr(grading_service, "enqueue_grading", lambda _id: None)


def fill(template: str, world: World, aliases: dict[str, str] | None = None) -> str:
    """Put the world's ids into `{name}` slots."""
    aliases = aliases or {}

    def lookup(match: re.Match) -> str:
        name = match.group(1)
        if name in world.users:
            return str(world.users[name].id)
        return world.ids[aliases.get(name, name)]

    return re.sub(r"\{(\w+)\}", lookup, template)


def fill_body(body, world: World):
    """`fill`, all the way down a JSON body."""
    if isinstance(body, str):
        return fill(body, world)
    if isinstance(body, list):
        return [fill_body(item, world) for item in body]
    if isinstance(body, dict):
        return {key: fill_body(value, world) for key, value in body.items()}
    return body


async def call(
    client: AsyncClient,
    world: World,
    key: str,
    actor: str | None,
    *,
    body: dict | None = None,
    params: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
):
    method, path = key.split(" ", 1)
    url = API + fill(path, world, params)
    return await client.request(
        method,
        url,
        headers=world.headers(actor) if actor else {},
        json=fill_body(body, world),
        params={name: fill(value, world) for name, value in (query or {}).items()},
    )


def keys_of(kind: type) -> list[str]:
    return sorted(key for key, rule in RULES.items() if isinstance(rule, kind))


# --- the tests ----------------------------------------------------------------


def test_every_route_is_classified(app: FastAPI) -> None:
    """A new route has to say who may call it before it can ship."""
    served = {key for key in app_routes(app) if not is_admin(key)}

    unclassified = served - RULES.keys()
    stale = RULES.keys() - served

    assert not unclassified, f"Thêm luật cho route mới vào RULES: {sorted(unclassified)}"
    assert not stale, f"Luật cho route không còn tồn tại: {sorted(stale)}"


def sign_in(route) -> str:
    """ "required", "optional" or "none": what the route's dependencies ask for."""

    def names(dependant):
        for sub in dependant.dependencies:
            yield getattr(sub.call, "__name__", "")
            yield from names(sub)

    found = set(names(route.dependant))
    if "get_current_user" in found:
        return "required"
    if "get_optional_user" in found:
        return "optional"
    return "none"


def test_the_table_and_the_code_agree_on_who_must_sign_in(app: FastAPI) -> None:
    """`Public` in the table and "no sign-in" in the code agree.

    Catches the other direction from the 401 sweep below: a route the table
    calls public that quietly grew a sign-in, or one that lost its guard and is
    now public without anybody deciding so. A route that only *looks at* who
    is asking (`OptionalUser`) may be either: a published course page is
    public, a lesson body behind it is not, and the sweep below holds the
    second kind to a refusal.
    """
    for key, route in app_routes(app).items():
        kind = sign_in(route)
        if is_admin(key):
            assert kind == "required", key
        elif isinstance(RULES[key], Public):
            assert kind != "required", f"{key}: bảng ghi công khai nhưng code đòi đăng nhập"
        else:
            assert kind != "none", f"{key}: bảng ghi cần đăng nhập nhưng code để công khai"


@pytest.mark.parametrize("key", sorted(k for k in RULES if not isinstance(RULES[k], Public)))
async def test_signed_out_is_refused(
    app: FastAPI, api_client: AsyncClient, world: World, key: str
) -> None:
    rule = RULES[key]
    response = await call(
        api_client,
        world,
        key,
        None,
        body=getattr(rule, "body", None),
        params=getattr(rule, "params", None),
        query=getattr(rule, "query", None),
    )

    if sign_in(app_routes(app)[key]) == "optional":
        assert response.status_code in REFUSED | {401}, response.text
    else:
        assert response.status_code == 401, response.text


@pytest.mark.parametrize("actor", ["learner", "teacher"])
async def test_admin_routes_refuse_everybody_else(
    app: FastAPI, api_client: AsyncClient, world: World, actor: str
) -> None:
    """The role check runs before anything reads the path, so any id will do."""
    for key in sorted(k for k in app_routes(app) if is_admin(k)):
        method, path = key.split(" ", 1)
        url = API + re.sub(r"\{\w+\}", str(uuid.uuid4()), path)
        response = await api_client.request(method, url, headers=world.headers(actor))
        assert response.status_code == 403, f"{key} as {actor}: {response.status_code}"


@pytest.mark.parametrize("key", keys_of(Owned))
async def test_outsiders_are_refused_and_the_owner_is_not(
    api_client: AsyncClient, world: World, key: str
) -> None:
    rule = RULES[key]
    assert isinstance(rule, Owned)
    request = {"body": rule.body, "params": rule.params, "query": rule.query}

    for outsider in rule.outsiders:
        response = await call(api_client, world, key, outsider, **request)
        assert response.status_code in rule.refused, (
            f"{key} as {outsider}: {response.status_code} {response.text[:300]}"
        )

    response = await call(api_client, world, key, rule.owner, **request)
    assert response.status_code not in DENIED, (
        f"{key} as owner {rule.owner}: {response.status_code} {response.text[:300]}"
    )


@pytest.mark.parametrize("key", keys_of(Scoped))
async def test_self_scoped_routes_answer_about_the_caller_only(
    api_client: AsyncClient, world: World, key: str
) -> None:
    rule = RULES[key]
    assert isinstance(rule, Scoped)

    response = await call(
        api_client,
        world,
        key,
        rule.actor,
        body=rule.body,
        params=rule.params,
        query=rule.query,
    )

    assert response.status_code not in {401, 422}, (
        f"{key}: {response.status_code} {response.text[:300]}"
    )
    for secret in rule.secrets:
        assert world.ids[secret] not in response.text, f"{key} as {rule.actor} leaks {secret}"


@pytest.mark.parametrize("key", keys_of(Open))
async def test_open_routes_let_any_signed_in_user_through(
    api_client: AsyncClient, world: World, key: str
) -> None:
    rule = RULES[key]
    assert isinstance(rule, Open)
    response = await call(api_client, world, key, rule.actor, body=rule.body)

    assert response.status_code not in DENIED, (
        f"{key}: {response.status_code} {response.text[:300]}"
    )
