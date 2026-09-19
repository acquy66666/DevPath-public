"""The course assistant over HTTP.

The model and the embedder are fakes: whether Gemini answers well is measured
live in `docs/report/assets/phase-4/chat-api.txt`, and whether *this code*
refuses the right people, streams events in the right order and stores the
right rows is a question a live model would answer no better while costing
quota.

The tests that matter most are the refusals that happen before any stream:
a student who is not enrolled, a course that has been unpublished since the
conversation began, somebody else's conversation. Each asserts that the model
was never called -- a refusal that still paid for a generation would be a
refusal in name only.
"""

import json
import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    Category,
    ChatMessage,
    ChatSession,
    Course,
    CourseSection,
    DocChunk,
    Enrollment,
    Lesson,
    User,
)
from app.models.rag import EMBEDDING_DIMENSIONS
from app.services.chat import NO_MATERIAL_ANSWER, UNAVAILABLE_MESSAGE
from app.services.llm import (
    LLMNotConfiguredError,
    LLMUnavailableError,
    get_chat_model_factory,
    get_embedder_factory,
)
from app.services.rate_limit import get_rate_limiter
from tests.api.fakes import MemoryRateLimiter

PASSWORD = "mật-khẩu-đủ-dài"
MODEL = "fake-embedding-001"


def at_angle(degrees: float) -> list[float]:
    radians = math.radians(degrees)
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[0] = math.cos(radians)
    vector[1] = math.sin(radians)
    return vector


class FakeEmbedder:
    def __init__(self) -> None:
        self.questions: list[list[str]] = []
        self.fail = False

    @property
    def model(self) -> str:
        return MODEL

    async def embed_documents(self, texts):
        raise AssertionError("asking must not embed documents")

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_queries([text]))[0]

    async def embed_queries(self, texts) -> list[list[float]]:
        if self.fail:
            raise LLMUnavailableError("Gọi Gemini thất bại (HTTP 429: quota)")
        self.questions.append(list(texts))
        return [at_angle(0) for _ in texts]


class FakeChatModel:
    """Answers with the pieces it is given, and remembers every prompt."""

    def __init__(self) -> None:
        self.pieces = ["Biến được tạo ", "khi gán giá trị [1]."]
        self.fail_after: int | None = None
        self.calls: list[dict] = []

    @property
    def model(self) -> str:
        return "fake-chat"

    async def stream(self, *, system, turns):
        self.calls.append({"system": system, "turns": list(turns)})
        for index, piece in enumerate(self.pieces):
            if self.fail_after is not None and index >= self.fail_after:
                raise LLMUnavailableError("Gemini ngắt giữa câu trả lời (HTTP 503)")
            yield piece


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def chat_model() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
def llm(app: FastAPI, api_client: AsyncClient, embedder, chat_model) -> None:
    """Point the routes at the fakes. Depends on `api_client` so that its
    teardown -- which clears every override -- runs after these are set."""
    app.dependency_overrides[get_embedder_factory] = lambda: lambda: embedder
    app.dependency_overrides[get_chat_model_factory] = lambda: lambda: chat_model


async def make_user(session: AsyncSession, role: str = "student") -> User:
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


async def make_course(
    session: AsyncSession, instructor: User, *, with_material: bool = True
) -> Course:
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title="Lập trình Python cơ bản",
        slug=f"python-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1: Làm quen", position=0)
    session.add(section)
    await session.flush()

    for position, (title, text, angle) in enumerate(
        [
            ("Biến trong Python", "Biến được tạo khi gán giá trị.", 5),
            ("Vòng lặp for", "for duyệt qua từng phần tử.", 50),
        ]
    ):
        lesson = Lesson(
            section_id=section.id,
            title=title,
            type="article",
            position=position,
            article_content=text,
        )
        session.add(lesson)
        await session.flush()
        if with_material:
            session.add(
                DocChunk(
                    course_id=course.id,
                    lesson_id=lesson.id,
                    chunk_index=0,
                    content=f"{title}\n\n{text}",
                    token_count=12,
                    embedding=at_angle(angle),
                    embedding_model=MODEL,
                )
            )
    await session.flush()
    return course


@pytest.fixture
async def instructor(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def course(db_session: AsyncSession, instructor: User) -> Course:
    return await make_course(db_session, instructor)


@pytest.fixture
async def student_user(db_session: AsyncSession, course: Course) -> User:
    user = await make_user(db_session)
    db_session.add(Enrollment(user_id=user.id, course_id=course.id))
    await db_session.flush()
    return user


@pytest.fixture
async def student(api_client: AsyncClient, student_user: User) -> dict[str, str]:
    return await sign_in(api_client, student_user)


async def new_session(client: AsyncClient, course: Course, headers) -> dict:
    response = await client.post(
        f"/api/v1/courses/{course.id}/chat-sessions", headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for frame in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in frame.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


async def ask(client: AsyncClient, session_id: str, headers, question: str = "Biến là gì?"):
    return await client.post(
        f"/api/v1/chat-sessions/{session_id}/messages",
        json={"content": question},
        headers=headers,
    )


# --- Asking -------------------------------------------------------------------


async def test_an_answer_streams_sources_then_pieces_then_the_stored_message(
    api_client: AsyncClient, llm, student, course: Course, db_session: AsyncSession
) -> None:
    chat_session = await new_session(api_client, course, student)

    response = await ask(api_client, chat_session["id"], student)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"

    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "delta", "delta", "done"]

    sources = events[0][1]["sources"]
    assert [(s["number"], s["lesson_title"]) for s in sources] == [
        (1, "Biến trong Python"),
        (2, "Vòng lặp for"),
    ]
    assert sources[0]["score"] == pytest.approx(math.cos(math.radians(5)), abs=1e-3)

    streamed = "".join(data["text"] for name, data in events if name == "delta")
    done = events[-1][1]
    assert done["message"]["content"] == streamed == "Biến được tạo khi gán giá trị [1]."
    assert done["cited_numbers"] == [1]
    assert done["message"]["cited_lesson_ids"] == [sources[0]["lesson_id"]]

    stored = list(
        await db_session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == uuid.UUID(chat_session["id"]))
            .order_by(ChatMessage.created_at)
        )
    )
    assert [(m.role, m.content) for m in stored] == [
        ("user", "Biến là gì?"),
        ("assistant", streamed),
    ]
    assert stored[0].created_at < stored[1].created_at


async def test_the_model_is_given_the_rules_the_material_and_the_question(
    api_client: AsyncClient, llm, student, course: Course, chat_model: FakeChatModel
) -> None:
    chat_session = await new_session(api_client, course, student)

    await ask(api_client, chat_session["id"], student, "  Biến là gì?  ")

    call = chat_model.calls[0]
    assert "Lập trình Python cơ bản" in call["system"]
    last = call["turns"][-1].text
    assert '<nguon so="1" bai="Biến trong Python"' in last
    assert last.endswith("Biến là gì?")


async def test_a_refusal_is_stored_without_the_citations_the_model_gave_it(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    chat_model: FakeChatModel,
    db_session: AsyncSession,
) -> None:
    """Rule 3: a refusal cites nothing. When the model cites anyway -- 3 of 18
    refusals in the evaluation, while suggesting other topics -- the marks are
    dropped from what is stored, so the page shows no "sources" under an
    answer that says there are none. `done` carries the cleaned message, and
    that is what replaces the streamed text on the page."""
    chat_model.pieces = [
        "Xin lỗi bạn, nội dung này nằm ngoài phạm vi tài liệu của khóa học. ",
        "Bạn có thể hỏi về biến [1] hoặc vòng lặp for [2] nhé!",
    ]
    chat_session = await new_session(api_client, course, student)

    response = await ask(api_client, chat_session["id"], student, "Decorator là gì?")

    done = parse_sse(response.text)[-1]
    assert done[0] == "done"
    assert done[1]["cited_numbers"] == []
    assert done[1]["message"]["cited_lesson_ids"] == []
    assert done[1]["message"]["citations"] == []
    assert "[1]" not in done[1]["message"]["content"]
    assert done[1]["message"]["content"].endswith("hỏi về biến hoặc vòng lặp for nhé!")

    stored = await db_session.scalar(
        select(ChatMessage).where(
            ChatMessage.session_id == uuid.UUID(chat_session["id"]),
            ChatMessage.role == "assistant",
        )
    )
    assert stored.cited_lesson_ids == []
    assert "[2]" not in stored.content


async def test_a_follow_up_carries_the_conversation_so_far(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    chat_model: FakeChatModel,
    embedder: FakeEmbedder,
) -> None:
    chat_session = await new_session(api_client, course, student)
    await ask(api_client, chat_session["id"], student, "Biến là gì?")
    await ask(api_client, chat_session["id"], student, "Cho ví dụ?")

    turns = chat_model.calls[1]["turns"]
    assert [(turn.role, turn.text) for turn in turns[:2]] == [
        ("user", "Biến là gì?"),
        ("model", "Biến được tạo khi gán giá trị."),  # citation mark stripped
    ]
    assert turns[2].text.endswith("Cho ví dụ?")
    # The follow-up is searched alone and together with the question before
    # it, in one embedding call.
    assert embedder.questions == [
        ["Biến là gì?"],
        ["Cho ví dụ?", "Biến là gì?\nCho ví dụ?"],
    ]


async def test_each_search_reports_its_own_best_score(
    api_client: AsyncClient,
    llm,
    student,
    student_user: User,
    course: Course,
    chat_model: FakeChatModel,
    db_session: AsyncSession,
) -> None:
    """Merging keeps each passage at its better score, so the merged list
    cannot tell an off-topic follow-up (weak alone, strong when paired with
    the question before it) from a vague one. The chatbot evaluation needs
    both numbers to decide where a refusal threshold could sit."""
    from app.services.chat import prepare_answer

    chat_session = await new_session(api_client, course, student)
    await ask(api_client, chat_session["id"], student, "Biến là gì?")

    class AngleEmbedder(FakeEmbedder):
        async def embed_queries(self, texts):
            # Alone: 30° from the nearest lesson (50°). Paired: on top of the 5° one.
            return [at_angle(80), at_angle(5)][: len(texts)]

    prepared = await prepare_answer(
        db_session,
        uuid.UUID(chat_session["id"]),
        student_user,
        "Còn phở bò?",
        limiter=MemoryRateLimiter(),
        make_embedder=AngleEmbedder,
        make_chat_model=lambda: chat_model,
    )

    assert prepared.search_scores == pytest.approx(
        [math.cos(math.radians(30)), 1.0], abs=1e-6
    )
    assert prepared.sources[0].score == pytest.approx(1.0, abs=1e-6)


async def test_the_first_answered_question_names_the_conversation(
    api_client: AsyncClient, llm, student, course: Course
) -> None:
    chat_session = await new_session(api_client, course, student)
    assert chat_session["title"] is None

    await ask(api_client, chat_session["id"], student, "Biến là gì?")
    await ask(api_client, chat_session["id"], student, "Còn hằng số?")

    listed = await api_client.get(
        f"/api/v1/courses/{course.id}/chat-sessions", headers=student
    )
    assert listed.json()["items"][0]["title"] == "Biến là gì?"


async def test_a_course_without_material_answers_without_calling_the_model(
    api_client: AsyncClient,
    llm,
    db_session: AsyncSession,
    instructor: User,
    chat_model: FakeChatModel,
) -> None:
    empty = await make_course(db_session, instructor, with_material=False)
    user = await make_user(db_session)
    db_session.add(Enrollment(user_id=user.id, course_id=empty.id))
    await db_session.flush()
    headers = await sign_in(api_client, user)
    chat_session = await new_session(api_client, empty, headers)

    events = parse_sse((await ask(api_client, chat_session["id"], headers)).text)

    assert events[0] == ("sources", {"sources": []})
    assert events[1] == ("delta", {"text": NO_MATERIAL_ANSWER})
    assert events[-1][1]["cited_numbers"] == []
    assert chat_model.calls == []


async def test_a_model_that_fails_halfway_ends_with_an_error_and_stores_nothing(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    chat_model: FakeChatModel,
    db_session: AsyncSession,
) -> None:
    chat_model.fail_after = 1
    chat_session = await new_session(api_client, course, student)

    response = await ask(api_client, chat_session["id"], student)

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "delta", "error"]
    assert events[-1][1] == {"code": "LLM_UNAVAILABLE", "message": UNAVAILABLE_MESSAGE}
    # The upstream detail is for the log, not for the student.
    assert "503" not in response.text

    count = await db_session.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.session_id == uuid.UUID(chat_session["id"])
        )
    )
    assert count == 0


async def test_an_answer_that_cannot_be_stored_still_ends_the_stream_with_an_error(
    app: FastAPI,
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    db_session: AsyncSession,
) -> None:
    """The conversation is deleted in another tab while the answer streams.
    The stream promised to end with `done` or `error`; a failed write must
    not turn that into a stream that simply stops."""
    chat_session = await new_session(api_client, course, student)
    session_id = uuid.UUID(chat_session["id"])

    class DeletedMidAnswer(FakeChatModel):
        async def stream(self, *, system, turns):
            await db_session.execute(delete(ChatSession).where(ChatSession.id == session_id))
            yield "Một câu trả lời không còn chỗ để lưu."

    app.dependency_overrides[get_chat_model_factory] = lambda: DeletedMidAnswer

    response = await ask(api_client, chat_session["id"], student)

    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "delta", "error"]
    assert events[-1][1]["code"] == "CHAT_NOT_SAVED"


async def test_an_embedding_failure_is_refused_before_the_stream(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    embedder: FakeEmbedder,
    chat_model: FakeChatModel,
) -> None:
    embedder.fail = True
    chat_session = await new_session(api_client, course, student)

    response = await ask(api_client, chat_session["id"], student)

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "LLM_UNAVAILABLE",
        "message": UNAVAILABLE_MESSAGE,
    }
    assert chat_model.calls == []


async def test_without_a_key_the_refusal_says_so(
    app: FastAPI, api_client: AsyncClient, llm, student, course: Course
) -> None:
    chat_session = await new_session(api_client, course, student)

    def not_configured():
        raise LLMNotConfiguredError("Chưa cấu hình GEMINI_API_KEY")

    app.dependency_overrides[get_chat_model_factory] = lambda: not_configured

    response = await ask(api_client, chat_session["id"], student)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LLM_NOT_CONFIGURED"


async def test_without_a_key_a_stranger_is_still_told_to_sign_in(
    app: FastAPI, api_client: AsyncClient, llm, student, course: Course
) -> None:
    """The factories exist for this: a missing key must not outrank a
    missing login."""
    chat_session = await new_session(api_client, course, student)

    def not_configured():
        raise LLMNotConfiguredError("Chưa cấu hình GEMINI_API_KEY")

    app.dependency_overrides[get_chat_model_factory] = lambda: not_configured
    app.dependency_overrides[get_embedder_factory] = lambda: not_configured

    response = await ask(api_client, chat_session["id"], {})

    assert response.status_code == 401


# --- Who may ask --------------------------------------------------------------


async def test_a_student_who_is_not_enrolled_cannot_start_a_conversation(
    api_client: AsyncClient, llm, db_session: AsyncSession, course: Course
) -> None:
    outsider = await sign_in(api_client, await make_user(db_session))

    response = await api_client.post(
        f"/api/v1/courses/{course.id}/chat-sessions", headers=outsider
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_ENROLLED"


async def test_the_instructor_of_the_course_is_not_an_enrolled_student(
    api_client: AsyncClient, llm, instructor: User, course: Course
) -> None:
    headers = await sign_in(api_client, instructor)

    response = await api_client.post(
        f"/api/v1/courses/{course.id}/chat-sessions", headers=headers
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_ENROLLED"


async def test_a_course_unpublished_mid_conversation_stops_answering(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    db_session: AsyncSession,
    chat_model: FakeChatModel,
    embedder: FakeEmbedder,
) -> None:
    """The case the ingest job leaves behind on purpose: the chunks are still
    in the table, the student is still enrolled, the course is no longer
    published. Refused before any quota is spent."""
    chat_session = await new_session(api_client, course, student)
    course.status = "draft"
    await db_session.flush()

    response = await ask(api_client, chat_session["id"], student)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"
    assert embedder.questions == []
    assert chat_model.calls == []


async def test_a_course_that_does_not_exist_is_not_found(
    api_client: AsyncClient, llm, student
) -> None:
    response = await api_client.post(
        f"/api/v1/courses/{uuid.uuid4()}/chat-sessions", headers=student
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_someone_elses_conversation_is_not_found_by_any_route(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    db_session: AsyncSession,
    chat_model: FakeChatModel,
) -> None:
    chat_session = await new_session(api_client, course, student)
    other = await make_user(db_session)
    db_session.add(Enrollment(user_id=other.id, course_id=course.id))
    await db_session.flush()
    intruder = await sign_in(api_client, other)
    url = f"/api/v1/chat-sessions/{chat_session['id']}"

    responses = [
        await ask(api_client, chat_session["id"], intruder),
        await api_client.get(f"{url}/messages", headers=intruder),
        await api_client.delete(url, headers=intruder),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404]
    assert {r.json()["detail"]["code"] for r in responses} == {"CHAT_SESSION_NOT_FOUND"}
    assert chat_model.calls == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/courses/{course}/chat-sessions"),
        ("get", "/api/v1/courses/{course}/chat-sessions"),
        ("get", "/api/v1/chat-sessions/{session}/messages"),
        ("delete", "/api/v1/chat-sessions/{session}"),
        ("post", "/api/v1/chat-sessions/{session}/messages"),
    ],
)
async def test_every_route_needs_a_signed_in_user(
    api_client: AsyncClient, llm, course: Course, method: str, path: str
) -> None:
    url = path.format(course=course.id, session=uuid.uuid4())
    kwargs = {"json": {"content": "?"}} if method == "post" else {}

    response = await getattr(api_client, method)(url, **kwargs)

    assert response.status_code == 401


@pytest.mark.parametrize("content", ["", "   \n ", "x" * 2001])
async def test_a_question_must_have_words_and_fit(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    content: str,
    chat_model: FakeChatModel,
) -> None:
    chat_session = await new_session(api_client, course, student)

    response = await ask(api_client, chat_session["id"], student, content)

    assert response.status_code == 422
    assert chat_model.calls == []


async def test_asking_again_too_soon_is_refused_with_a_wait(
    app: FastAPI,
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    chat_model: FakeChatModel,
) -> None:
    limiter = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    chat_session = await new_session(api_client, course, student)

    first = await ask(api_client, chat_session["id"], student)
    second = await ask(api_client, chat_session["id"], student)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "CHAT_RATE_LIMITED"
    assert int(second.headers["retry-after"]) > 0
    assert len(chat_model.calls) == 1


# --- Reading back -------------------------------------------------------------


async def test_a_conversation_reads_back_oldest_first(
    api_client: AsyncClient, llm, student, course: Course
) -> None:
    chat_session = await new_session(api_client, course, student)
    await ask(api_client, chat_session["id"], student, "Câu một?")
    await ask(api_client, chat_session["id"], student, "Câu hai?")

    response = await api_client.get(
        f"/api/v1/chat-sessions/{chat_session['id']}/messages", headers=student
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert [(m["role"], m["content"]) for m in body["items"]][::2] == [
        ("user", "Câu một?"),
        ("user", "Câu hai?"),
    ]
    assert [m["role"] for m in body["items"]] == ["user", "assistant"] * 2


async def test_a_conversation_read_back_says_which_lesson_each_mark_is(
    api_client: AsyncClient, llm, student, course: Course, chat_model: FakeChatModel
) -> None:
    """The page links `[n]` in an old answer to a lesson. The stream told it
    what n meant at the time; reading back, only this field can."""
    chat_model.pieces = ["Vòng lặp duyệt từng phần tử [2], ", "biến thì gán [1]."]
    chat_session = await new_session(api_client, course, student)
    streamed = parse_sse((await ask(api_client, chat_session["id"], student)).text)
    lesson_of = {s["number"]: s["lesson_id"] for s in streamed[0][1]["sources"]}

    response = await api_client.get(
        f"/api/v1/chat-sessions/{chat_session['id']}/messages", headers=student
    )

    question, answer = response.json()["items"]
    expected = [
        {"number": 2, "lesson_id": lesson_of[2]},
        {"number": 1, "lesson_id": lesson_of[1]},
    ]
    assert answer["citations"] == expected
    assert question["citations"] == []
    # The stream's last event carries the same mapping as the read-back.
    assert streamed[-1][1]["message"]["citations"] == expected


async def test_conversations_list_only_your_own_most_recent_first(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    db_session: AsyncSession,
) -> None:
    older = await new_session(api_client, course, student)
    newer = await new_session(api_client, course, student)
    await ask(api_client, older["id"], student, "Hỏi sau cùng")  # now most recent

    other = await make_user(db_session)
    db_session.add(Enrollment(user_id=other.id, course_id=course.id))
    await db_session.flush()
    await new_session(api_client, course, await sign_in(api_client, other))

    response = await api_client.get(
        f"/api/v1/courses/{course.id}/chat-sessions",
        params={"page_size": 1},
        headers=student,
    )

    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [older["id"]]
    second_page = await api_client.get(
        f"/api/v1/courses/{course.id}/chat-sessions",
        params={"page": 2, "page_size": 1},
        headers=student,
    )
    assert [item["id"] for item in second_page.json()["items"]] == [newer["id"]]


async def test_deleting_a_conversation_takes_its_messages_with_it(
    api_client: AsyncClient,
    llm,
    student,
    course: Course,
    db_session: AsyncSession,
) -> None:
    chat_session = await new_session(api_client, course, student)
    await ask(api_client, chat_session["id"], student)

    response = await api_client.delete(
        f"/api/v1/chat-sessions/{chat_session['id']}", headers=student
    )

    assert response.status_code == 204
    session_id = uuid.UUID(chat_session["id"])
    assert await db_session.get(ChatSession, session_id) is None
    remaining = await db_session.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.session_id == session_id
        )
    )
    assert remaining == 0
