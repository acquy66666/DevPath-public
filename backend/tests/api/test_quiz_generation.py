"""Drafting quiz questions with a model, and the review that stands between
those drafts and a student.

The model is a fake: which model writes *good* questions was measured live
(docs/report/assets/phase-4/quiz-generation.txt), and what these tests ask is
whether this code believes the right parts of an answer, stores drafts as
drafts, and refuses to publish one nobody read. That last rule is why the
feature is safe to have at all -- the cheaper model was measured writing a
wrong answer key that looked right.

Every refusal that happens before the model is called asserts that it was not
called: a refusal that still spent the quota is only half a refusal.
"""

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    Category,
    Course,
    CourseSection,
    Lesson,
    Quiz,
    QuizQuestion,
    User,
    VideoAsset,
)
from app.services.llm import LLMNotConfiguredError, LLMUnavailableError, get_quiz_model_factory
from app.services.rate_limit import get_rate_limiter
from app.services.storage import get_storage_factory
from tests.api.fakes import FakeStorage, MemoryRateLimiter

PASSWORD = "mật-khẩu-đủ-dài"
ARTICLE = (
    "`input()` luôn trả về chuỗi. `int(\"12\")` cho ra 12, nhưng `int(\"12.5\")` thì lỗi. "
    "Khi làm việc với tiền, dùng `Decimal`."
)
TRANSCRIPT = (
    "1\n00:00:01,000 --> 00:00:04,000\nVòng lặp for duyệt qua từng phần tử\n\n"
    "2\n00:00:04,000 --> 00:00:07,000\ncủa một danh sách, theo thứ tự.\n"
)


def drafted(question: str, correct: str = "str", explanation: str = "Theo tài liệu.") -> dict:
    """A well-formed question whose right answer is `correct`."""
    wrong = [option for option in ["int", "float", "bool", "list", "str"] if option != correct]
    return {
        "question": question,
        "options": [correct, *wrong[:3]],
        "correct_index": 0,
        "explanation": explanation,
    }


class FakeQuizModel:
    """Answers with whatever document it is given, and remembers every prompt."""

    def __init__(self) -> None:
        self.document: object = {
            "questions": [
                drafted("Hàm `input()` trả về kiểu gì?"),
                drafted("Nên dùng kiểu nào cho tiền?", correct="Decimal"),
            ]
        }
        self.fail: Exception | None = None
        self.calls: list[dict] = []

    @property
    def model(self) -> str:
        return "fake-quiz"

    async def generate(self, *, system, prompt, schema):
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        if self.fail:
            raise self.fail
        return self.document


@pytest.fixture
def quiz_model() -> FakeQuizModel:
    return FakeQuizModel()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def fakes(app: FastAPI, api_client: AsyncClient, quiz_model, storage) -> None:
    """Depends on `api_client` so its teardown, which clears every override,
    runs after these are set."""
    app.dependency_overrides[get_quiz_model_factory] = lambda: lambda: quiz_model
    app.dependency_overrides[get_storage_factory] = lambda: lambda: storage


async def make_user(session: AsyncSession, role: str) -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=role.title(),
        password_hash=hash_password(PASSWORD),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def sign_in(client: AsyncClient, user: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_course(session: AsyncSession, instructor: User) -> dict:
    """A course with an article, a video with a transcript, an empty video,
    and a quiz lesson holding an empty draft quiz."""
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()
    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title="Python cơ bản",
        slug=f"python-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()
    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    lessons = {}
    for position, (key, title, kind) in enumerate(
        [
            ("article", "Ép kiểu và những cái bẫy quen thuộc", "article"),
            ("video", "Vòng lặp for", "video"),
            ("silent", "Video chưa có lời", "video"),
            ("quiz", "Kiểm tra chương 1", "quiz"),
        ]
    ):
        lesson = Lesson(
            section_id=section.id,
            title=title,
            type=kind,
            position=position,
            article_content=ARTICLE if kind == "article" else None,
        )
        session.add(lesson)
        await session.flush()
        lessons[key] = lesson

    quiz = Quiz(lesson_id=lessons["quiz"].id)
    session.add(quiz)
    await session.flush()
    return {"course": course, "lessons": lessons, "quiz": quiz}


@pytest.fixture
async def owner_user(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def owner(api_client: AsyncClient, owner_user: User) -> dict[str, str]:
    return await sign_in(api_client, owner_user)


@pytest.fixture
async def world(db_session: AsyncSession, owner_user: User, storage: FakeStorage) -> dict:
    built = await make_course(db_session, owner_user)
    asset_id = uuid.uuid4()
    key = f"videos/{asset_id}/transcript.srt"
    asset = VideoAsset(
        id=asset_id,
        storage_key=f"videos/{asset_id}/original.mp4",
        status="ready",
        transcript_key=key,
    )
    db_session.add(asset)
    built["lessons"]["video"].video_asset = asset
    await db_session.flush()
    storage.objects[key] = (TRANSCRIPT.encode("utf-8"), "application/x-subrip")
    return built


async def generate(
    client: AsyncClient, world: dict, headers, *, source: str = "article", count: int = 2
):
    return await client.post(
        f"/api/v1/quizzes/{world['quiz'].id}/generate",
        json={"source_lesson_id": str(world["lessons"][source].id), "count": count},
        headers=headers,
    )


async def stored(session: AsyncSession, quiz: Quiz) -> list[QuizQuestion]:
    return list(
        await session.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.position)
            .execution_options(populate_existing=True)
        )
    )


# --- Generating -----------------------------------------------------------------


async def test_drafts_are_stored_as_unreviewed_ai_questions(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession, quiz_model
) -> None:
    response = await generate(api_client, world, owner)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["requested"], body["created"], body["dropped"]) == (2, 2, 0)
    assert body["model"] == "fake-quiz"
    assert body["truncated"] is False
    assert [q["ai_generated"] for q in body["questions"]] == [True, True]
    assert [q["reviewed_at"] for q in body["questions"]] == [None, None]

    rows = await stored(db_session, world["quiz"])
    assert [row.question for row in rows] == [
        "Hàm `input()` trả về kiểu gì?",
        "Nên dùng kiểu nào cho tiền?",
    ]
    assert [row.position for row in rows] == [0, 1]
    # Shuffled or not, the right answer is still the right answer.
    assert [row.options[row.correct_index] for row in rows] == ["str", "Decimal"]
    await db_session.refresh(world["quiz"])
    assert world["quiz"].ai_generated is True


async def test_the_model_reads_the_lesson_and_is_told_how_many(
    api_client: AsyncClient, fakes, owner, world, quiz_model
) -> None:
    await generate(api_client, world, owner, count=3)

    call = quiz_model.calls[0]
    assert "`input()` luôn trả về chuỗi." in call["prompt"]
    assert "Ép kiểu và những cái bẫy quen thuộc" in call["prompt"]
    assert "3 câu hỏi" in call["prompt"]
    assert call["schema"]["properties"]["questions"]["maxItems"] == 3


async def test_a_video_is_read_from_its_transcript(
    api_client: AsyncClient, fakes, owner, world, quiz_model
) -> None:
    response = await generate(api_client, world, owner, source="video")

    assert response.status_code == 201, response.text
    assert "Vòng lặp for duyệt qua từng phần tử" in quiz_model.calls[0]["prompt"]
    assert "00:00:01,000" not in quiz_model.calls[0]["prompt"]


async def test_new_drafts_go_after_what_the_quiz_has_and_avoid_repeating_it(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession, quiz_model
) -> None:
    db_session.add(
        QuizQuestion(
            quiz_id=world["quiz"].id,
            question="Hàm `input()` trả về kiểu gì?",
            options=["str", "int"],
            correct_index=0,
            position=0,
        )
    )
    await db_session.flush()

    body = (await generate(api_client, world, owner)).json()

    assert "Hàm `input()` trả về kiểu gì?" in quiz_model.calls[0]["prompt"]
    assert (body["created"], body["dropped"]) == (1, 1)
    rows = await stored(db_session, world["quiz"])
    assert [(row.position, row.ai_generated) for row in rows] == [(0, False), (1, True)]


async def test_a_question_with_no_right_answer_is_dropped_and_counted(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession, quiz_model
) -> None:
    broken = drafted("Câu hỏng?") | {"correct_index": 7}
    quiz_model.document = {"questions": [broken, drafted("Câu tốt?")]}

    body = (await generate(api_client, world, owner)).json()

    assert (body["created"], body["dropped"]) == (1, 1)
    assert [row.question for row in await stored(db_session, world["quiz"])] == ["Câu tốt?"]


async def test_nothing_usable_is_an_error_and_stores_nothing(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession, quiz_model
) -> None:
    quiz_model.document = {"questions": [drafted("Hỏng?") | {"options": ["a", "a"]}]}

    response = await generate(api_client, world, owner)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "QUIZ_GENERATION_FAILED"
    assert await stored(db_session, world["quiz"]) == []


async def test_the_model_failing_is_a_503_that_stores_nothing(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession, quiz_model
) -> None:
    quiz_model.fail = LLMUnavailableError("Gọi Gemini thất bại (HTTP 503)")

    response = await generate(api_client, world, owner)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LLM_UNAVAILABLE"
    assert await stored(db_session, world["quiz"]) == []


async def test_without_a_key_the_refusal_says_so(
    app: FastAPI, api_client: AsyncClient, fakes, owner, world
) -> None:
    def no_key():
        raise LLMNotConfiguredError("Chưa cấu hình GEMINI_API_KEY")

    app.dependency_overrides[get_quiz_model_factory] = lambda: no_key

    response = await generate(api_client, world, owner)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LLM_NOT_CONFIGURED"


# --- Refused before the model is called -----------------------------------------


async def test_a_lesson_with_no_words_is_refused(
    api_client: AsyncClient, fakes, owner, world, quiz_model
) -> None:
    for source in ("silent", "quiz"):
        response = await generate(api_client, world, owner, source=source)

        assert response.status_code == 409, source
        assert response.json()["detail"]["code"] == "LESSON_HAS_NO_TEXT"
    assert quiz_model.calls == []


async def test_a_lesson_from_another_course_is_refused(
    api_client: AsyncClient, fakes, owner, owner_user, world, db_session, quiz_model
) -> None:
    other = await make_course(db_session, owner_user)

    response = await api_client.post(
        f"/api/v1/quizzes/{world['quiz'].id}/generate",
        json={"source_lesson_id": str(other["lessons"]["article"].id), "count": 2},
        headers=owner,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SOURCE_NOT_IN_COURSE"
    assert quiz_model.calls == []


async def test_a_published_quiz_takes_no_drafts(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession, quiz_model
) -> None:
    world["quiz"].is_published = True
    await db_session.flush()

    response = await generate(api_client, world, owner)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUIZ_PUBLISHED"
    assert quiz_model.calls == []


async def test_only_the_owner_may_generate(
    api_client: AsyncClient, fakes, world, db_session: AsyncSession, quiz_model
) -> None:
    stranger = await sign_in(api_client, await make_user(db_session, "instructor"))
    student = await sign_in(api_client, await make_user(db_session, "student"))

    for headers in (stranger, student):
        assert (await generate(api_client, world, headers)).status_code == 403
    assert (await generate(api_client, world, {})).status_code == 401
    assert quiz_model.calls == []


async def test_the_count_is_bounded(api_client: AsyncClient, fakes, owner, world) -> None:
    for count in (0, 11):
        assert (await generate(api_client, world, owner, count=count)).status_code == 422


async def test_generating_again_too_soon_is_refused_with_a_wait(
    app: FastAPI, api_client: AsyncClient, fakes, owner, world, quiz_model
) -> None:
    limiter = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    first = await generate(api_client, world, owner)
    quiz_model.document = {"questions": [drafted("Câu khác hẳn?")]}
    second = await generate(api_client, world, owner)

    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "QUIZ_GENERATION_RATE_LIMITED"
    assert second.json()["detail"]["retry_after"] > 0
    assert len(quiz_model.calls) == 1


# --- Review stands between a draft and a student --------------------------------


async def publish(client: AsyncClient, world: dict, headers):
    return await client.patch(
        f"/api/v1/quizzes/{world['quiz'].id}", json={"is_published": True}, headers=headers
    )


async def test_a_quiz_with_an_unreviewed_draft_cannot_be_published(
    api_client: AsyncClient, fakes, owner, world
) -> None:
    await generate(api_client, world, owner)

    response = await publish(api_client, world, owner)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUIZ_NEEDS_REVIEW"
    assert "2" in response.json()["detail"]["message"]


async def test_approving_every_draft_allows_publishing(
    api_client: AsyncClient, fakes, owner, world
) -> None:
    questions = (await generate(api_client, world, owner)).json()["questions"]

    for question in questions:
        response = await api_client.post(
            f"/api/v1/quiz-questions/{question['id']}/approve", headers=owner
        )
        assert response.status_code == 200, response.text
        assert response.json()["reviewed_at"] is not None

    assert (await publish(api_client, world, owner)).status_code == 200


async def test_approving_twice_keeps_the_first_sign_off(
    api_client: AsyncClient, fakes, owner, world
) -> None:
    question = (await generate(api_client, world, owner)).json()["questions"][0]
    url = f"/api/v1/quiz-questions/{question['id']}/approve"

    first = (await api_client.post(url, headers=owner)).json()["reviewed_at"]
    second = (await api_client.post(url, headers=owner)).json()["reviewed_at"]

    assert first == second


async def test_editing_a_draft_counts_as_reviewing_it(
    api_client: AsyncClient, fakes, owner, world
) -> None:
    """The edit form shows the question, every option and the key; saving it
    is signing it."""
    question = (await generate(api_client, world, owner)).json()["questions"][0]

    response = await api_client.patch(
        f"/api/v1/quiz-questions/{question['id']}",
        json={"explanation": "Giảng viên viết lại lời giải thích."},
        headers=owner,
    )

    assert response.status_code == 200
    assert response.json()["reviewed_at"] is not None


async def test_deleting_the_drafts_nobody_wants_also_allows_publishing(
    api_client: AsyncClient, fakes, owner, world
) -> None:
    questions = (await generate(api_client, world, owner)).json()["questions"]
    await api_client.post(f"/api/v1/quiz-questions/{questions[0]['id']}/approve", headers=owner)
    await api_client.delete(f"/api/v1/quiz-questions/{questions[1]['id']}", headers=owner)

    assert (await publish(api_client, world, owner)).status_code == 200


async def test_only_a_draft_can_be_approved(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession
) -> None:
    typed = QuizQuestion(
        quiz_id=world["quiz"].id,
        question="Câu giảng viên tự gõ?",
        options=["a", "b"],
        correct_index=0,
        position=0,
    )
    db_session.add(typed)
    await db_session.flush()

    response = await api_client.post(f"/api/v1/quiz-questions/{typed.id}/approve", headers=owner)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUESTION_NOT_GENERATED"


async def test_only_the_owner_may_approve(
    api_client: AsyncClient, fakes, owner, world, db_session: AsyncSession
) -> None:
    question = (await generate(api_client, world, owner)).json()["questions"][0]
    stranger = await sign_in(api_client, await make_user(db_session, "instructor"))

    response = await api_client.post(
        f"/api/v1/quiz-questions/{question['id']}/approve", headers=stranger
    )

    assert response.status_code == 403


async def test_the_instructors_list_says_which_questions_are_drafts(
    api_client: AsyncClient, fakes, owner, world
) -> None:
    await generate(api_client, world, owner)

    listed = (
        await api_client.get(f"/api/v1/quizzes/{world['quiz'].id}/questions", headers=owner)
    ).json()

    assert [(q["ai_generated"], q["reviewed_at"]) for q in listed] == [(True, None)] * 2
    # And the response is JSON all the way down -- no datetime left unserialised.
    json.dumps(listed)
