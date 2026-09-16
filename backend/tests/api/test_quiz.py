"""Quizzes over HTTP: authoring, sitting one against a clock, and marking it.

Two tests carry this file. `test_a_student_never_receives_the_answer_key`
asserts against the raw response body rather than a parsed field, because the
leak that ships is the one in a key nobody thought to check. And the four
clock tests below it are the reason the feature exists at all: "giờ tính ở
backend" is only true if a request whose body is perfect and whose timing is
late is still refused, so that is what they do -- by moving `started_at` into
the past through the database, never by sleeping.

The constraint tests at the end go through SQL on purpose. One unfinished
attempt per student and "an expired attempt scores zero" are enforced by the
database, so they are tested where they live; a service that stopped checking
them would still pass an API test.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    Category,
    Course,
    Enrollment,
    LessonProgress,
    QuizAttempt,
    User,
)
from app.services.quiz import SUBMIT_GRACE_S

PASSWORD = "mật-khẩu-đủ-dài"
COURSES = "/api/v1/courses"
TIME_LIMIT_S = 600

# If either of these strings reaches a student mid-attempt, the quiz is
# worthless and the test that finds it says so by name.
SECRET_EXPLANATION = "SECRET-EXPLANATION-DO-NOT-LEAK"


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


@pytest.fixture
async def owner_user(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def owner(api_client: AsyncClient, owner_user: User) -> dict[str, str]:
    return await sign_in(api_client, owner_user)


@pytest.fixture
async def lesson(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner_user: User,
    owner: dict[str, str],
) -> dict:
    """A published course with one `quiz` lesson in it."""
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()

    course = Course(
        instructor_id=owner_user.id,
        category_id=category.id,
        title="Lập trình Python cơ bản",
        slug=f"python-co-ban-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    db_session.add(course)
    await db_session.flush()

    section = (
        await api_client.post(
            f"{COURSES}/{course.id}/sections", json={"title": "Chương 1"}, headers=owner
        )
    ).json()
    created = await api_client.post(
        f"/api/v1/sections/{section['id']}/lessons",
        json={"title": "Kiểm tra chương 1", "type": "quiz"},
        headers=owner,
    )
    assert created.status_code == 201, created.text
    return created.json() | {"course_id": str(course.id)}


async def add_question(
    client: AsyncClient,
    quiz_id: str,
    owner: dict[str, str],
    question: str,
    options: list[str],
    correct_index: int,
    explanation: str | None = None,
) -> dict:
    response = await client.post(
        f"/api/v1/quizzes/{quiz_id}/questions",
        json={
            "question": question,
            "options": options,
            "correct_index": correct_index,
            "explanation": explanation,
        },
        headers=owner,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def quiz(api_client: AsyncClient, lesson: dict, owner: dict[str, str]) -> dict:
    """A published quiz of two questions, one of which has an explanation."""
    created = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz",
        json={"time_limit_s": TIME_LIMIT_S, "pass_score": 50},
        headers=owner,
    )
    assert created.status_code == 201, created.text
    quiz = created.json()

    await add_question(
        api_client,
        quiz["id"],
        owner,
        "Kiểu dữ liệu nào lưu số nguyên trong Python?",
        ["int", "str", "list"],
        0,
        SECRET_EXPLANATION,
    )
    await add_question(
        api_client, quiz["id"], owner, "len('abc') trả về gì?", ["2", "3", "4"], 1
    )

    published = await api_client.patch(
        f"/api/v1/quizzes/{quiz['id']}", json={"is_published": True}, headers=owner
    )
    assert published.status_code == 200, published.text
    return published.json()


@pytest.fixture
async def student_user(db_session: AsyncSession, lesson: dict) -> User:
    """A student enrolled in the course, so the lesson is theirs to open."""
    user = await make_user(db_session, "student")
    db_session.add(Enrollment(user_id=user.id, course_id=uuid.UUID(lesson["course_id"])))
    await db_session.flush()
    return user


@pytest.fixture
async def student(api_client: AsyncClient, student_user: User) -> dict[str, str]:
    return await sign_in(api_client, student_user)


async def start(client: AsyncClient, quiz_id: str, headers: dict[str, str]) -> dict:
    response = await client.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def rewind(session: AsyncSession, attempt_id: str, seconds: int) -> None:
    """Move an attempt's start into the past.

    How every clock test here travels in time. Sleeping for ten minutes is not
    a test, and mocking `datetime.now` would prove the mock works rather than
    that the deadline does -- this changes the same column the service reads.
    """
    attempt = await session.get(QuizAttempt, uuid.UUID(attempt_id))
    attempt.started_at = datetime.now(UTC) - timedelta(seconds=seconds)
    await session.flush()


# --- Authoring -------------------------------------------------------------


async def test_an_instructor_builds_a_quiz_and_publishes_it(
    api_client: AsyncClient, quiz: dict
):
    assert quiz["is_published"] is True
    assert quiz["question_count"] == 2
    assert quiz["time_limit_s"] == TIME_LIMIT_S
    assert quiz["ai_generated"] is False


async def test_an_empty_quiz_cannot_be_published(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str]
):
    """Publishing it would show a student a page with nothing on it."""
    created = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz", json={}, headers=owner
    )
    response = await api_client.patch(
        f"/api/v1/quizzes/{created.json()['id']}",
        json={"is_published": True},
        headers=owner,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUIZ_EMPTY"


async def test_a_lesson_has_at_most_one_quiz(
    api_client: AsyncClient, lesson: dict, quiz: dict, owner: dict[str, str]
):
    response = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz", json={}, headers=owner
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUIZ_EXISTS"


async def test_a_question_cannot_point_past_its_own_options(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str]
):
    """Refused before it reaches the table, with a 422 that names the field."""
    created = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz", json={}, headers=owner
    )
    response = await api_client.post(
        f"/api/v1/quizzes/{created.json()['id']}/questions",
        json={"question": "2 + 2 = ?", "options": ["3", "4"], "correct_index": 7},
        headers=owner,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


async def test_shrinking_the_options_cannot_orphan_the_correct_answer(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str]
):
    """The rule is re-checked on the merged row, not on what was sent.

    The PATCH here is valid in isolation -- it only sends `options`. It is the
    combination with the `correct_index` already in the row that would leave a
    question whose right answer is off the end of its own list.
    """
    created = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz", json={}, headers=owner
    )
    question = await add_question(
        api_client, created.json()["id"], owner, "Chọn số lớn nhất", ["1", "2", "3"], 2
    )

    response = await api_client.patch(
        f"/api/v1/quiz-questions/{question['id']}",
        json={"options": ["1", "2"]},
        headers=owner,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_QUESTION"


async def test_the_questions_of_a_published_quiz_are_frozen(
    api_client: AsyncClient, quiz: dict, owner: dict[str, str]
):
    """Somebody may be sitting it; editing the key marks them on a question
    they were never shown."""
    questions = (
        await api_client.get(f"/api/v1/quizzes/{quiz['id']}/questions", headers=owner)
    ).json()

    response = await api_client.patch(
        f"/api/v1/quiz-questions/{questions[0]['id']}",
        json={"correct_index": 1},
        headers=owner,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUIZ_PUBLISHED"


async def test_a_quiz_being_sat_cannot_be_unpublished(
    api_client: AsyncClient, quiz: dict, owner: dict[str, str], student: dict[str, str]
):
    await start(api_client, quiz["id"], student)

    response = await api_client.patch(
        f"/api/v1/quizzes/{quiz['id']}", json={"is_published": False}, headers=owner
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ATTEMPT_IN_PROGRESS"


# --- The answer key --------------------------------------------------------


async def test_a_student_never_receives_the_answer_key(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    """The property the whole feature rests on, asserted against raw text.

    Not `"correct_index" not in parsed["questions"][0]` -- against the body,
    so that an answer key appearing in some field nobody thought to check is
    caught too.
    """
    response = await api_client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers=student
    )
    assert response.status_code == 201, response.text

    body = response.text
    assert SECRET_EXPLANATION not in body
    assert "correct_index" not in body
    assert "explanation" not in body

    attempt = response.json()
    assert len(attempt["questions"]) == 2
    assert attempt["review"] is None
    assert set(attempt["questions"][0]) == {"id", "position", "question", "options"}


async def test_a_student_cannot_read_the_question_bank(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    """The instructor's view of the questions is not a filtered shared route."""
    response = await api_client.get(
        f"/api/v1/quizzes/{quiz['id']}/questions", headers=student
    )
    assert response.status_code == 403
    assert SECRET_EXPLANATION not in response.text


async def test_reading_a_running_attempt_still_hides_the_answers(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    """Refreshing the page must not be a way around the rule above."""
    attempt = await start(api_client, quiz["id"], student)

    response = await api_client.get(
        f"/api/v1/quiz-attempts/{attempt['id']}", headers=student
    )
    assert response.status_code == 200
    assert SECRET_EXPLANATION not in response.text
    assert response.json()["review"] is None


# --- Sitting the quiz ------------------------------------------------------


async def test_the_quiz_is_marked_and_the_explanation_appears_after_submitting(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    attempt = await start(api_client, quiz["id"], student)

    response = await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [0, 1]},
        headers=student,
    )
    assert response.status_code == 200, response.text
    result = response.json()

    assert result["score"] == 100
    assert result["passed"] is True
    assert result["expired"] is False
    assert result["submitted_at"] is not None
    assert [row["is_correct"] for row in result["review"]] == [True, True]
    assert result["review"][0]["explanation"] == SECRET_EXPLANATION


async def test_a_half_right_paper_scores_half(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    attempt = await start(api_client, quiz["id"], student)

    result = (
        await api_client.post(
            f"/api/v1/quiz-attempts/{attempt['id']}/submit",
            json={"answers": [0, 2]},
            headers=student,
        )
    ).json()

    assert result["score"] == 50
    assert [row["is_correct"] for row in result["review"]] == [True, False]
    assert result["review"][1]["your_answer"] == 2
    assert result["review"][1]["correct_index"] == 1


async def test_a_skipped_question_is_simply_wrong(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    attempt = await start(api_client, quiz["id"], student)

    result = (
        await api_client.post(
            f"/api/v1/quiz-attempts/{attempt['id']}/submit",
            json={"answers": [0, None]},
            headers=student,
        )
    ).json()

    assert result["score"] == 50
    assert result["review"][1]["your_answer"] is None


async def test_answers_must_match_the_number_of_questions(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    attempt = await start(api_client, quiz["id"], student)

    response = await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [0]},
        headers=student,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_ANSWERS"


async def test_an_option_that_does_not_exist_is_refused(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    attempt = await start(api_client, quiz["id"], student)

    response = await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [9, 1]},
        headers=student,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_ANSWERS"


async def test_a_paper_cannot_be_handed_in_twice(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    attempt = await start(api_client, quiz["id"], student)
    await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [0, 1]},
        headers=student,
    )

    again = await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [0, 1]},
        headers=student,
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "ATTEMPT_ALREADY_SUBMITTED"


# --- The clock -------------------------------------------------------------


async def test_refreshing_does_not_start_a_second_clock(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    """Starting twice returns the same attempt, with less time left."""
    first = await start(api_client, quiz["id"], student)
    second = await start(api_client, quiz["id"], student)

    assert second["id"] == first["id"]
    assert second["started_at"] == first["started_at"]
    assert second["seconds_remaining"] <= first["seconds_remaining"]


async def test_the_deadline_comes_from_the_attempt_not_the_request(
    api_client: AsyncClient, quiz: dict, student: dict[str, str]
):
    attempt = await start(api_client, quiz["id"], student)

    started = datetime.fromisoformat(attempt["started_at"])
    deadline = datetime.fromisoformat(attempt["deadline_at"])
    assert (deadline - started).total_seconds() == TIME_LIMIT_S
    assert attempt["seconds_remaining"] <= TIME_LIMIT_S


async def test_answers_arriving_after_the_deadline_score_zero(
    api_client: AsyncClient,
    db_session: AsyncSession,
    quiz: dict,
    student: dict[str, str],
):
    """A perfect paper, handed in far too late.

    Every answer is right and the score is still zero: the clock is read
    before the answers are, which is the difference between a time limit and
    a suggestion the client is asked to honour.
    """
    attempt = await start(api_client, quiz["id"], student)
    await rewind(db_session, attempt["id"], TIME_LIMIT_S + 3600)

    response = await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [0, 1]},
        headers=student,
    )
    assert response.status_code == 200, response.text
    result = response.json()

    assert result["expired"] is True
    assert result["score"] == 0
    assert result["passed"] is False
    assert [row["your_answer"] for row in result["review"]] == [None, None]


async def test_a_late_answer_within_the_grace_window_is_still_marked(
    api_client: AsyncClient,
    db_session: AsyncSession,
    quiz: dict,
    student: dict[str, str],
):
    """The round trip is not the student's fault.

    Submitted a few seconds past the deadline but inside the grace window:
    marked normally, and not flagged as expired.
    """
    attempt = await start(api_client, quiz["id"], student)
    await rewind(db_session, attempt["id"], TIME_LIMIT_S + SUBMIT_GRACE_S - 5)

    result = (
        await api_client.post(
            f"/api/v1/quiz-attempts/{attempt['id']}/submit",
            json={"answers": [0, 1]},
            headers=student,
        )
    ).json()

    assert result["expired"] is False
    assert result["score"] == 100


async def test_an_abandoned_attempt_is_closed_so_the_next_one_can_start(
    api_client: AsyncClient,
    db_session: AsyncSession,
    quiz: dict,
    student: dict[str, str],
):
    """Nobody submitted, and the slot still has to be released.

    Without this the partial unique index would lock the student out of their
    own quiz for good -- one unfinished attempt, forever.
    """
    abandoned = await start(api_client, quiz["id"], student)
    await rewind(db_session, abandoned["id"], TIME_LIMIT_S + 3600)

    fresh = await start(api_client, quiz["id"], student)
    assert fresh["id"] != abandoned["id"]
    assert fresh["submitted_at"] is None

    closed = (
        await api_client.get(f"/api/v1/quiz-attempts/{abandoned['id']}", headers=student)
    ).json()
    assert closed["expired"] is True
    assert closed["score"] == 0
    # Ended when the time ran out, not when somebody happened to look at it.
    assert closed["submitted_at"] == closed["deadline_at"]


async def test_an_untimed_quiz_has_no_deadline(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str], student: dict[str, str]
):
    """A self-check at the end of a chapter is a legitimate quiz."""
    created = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz", json={"time_limit_s": None}, headers=owner
    )
    quiz_id = created.json()["id"]
    await add_question(api_client, quiz_id, owner, "1 + 1 = ?", ["1", "2"], 1)
    await api_client.patch(
        f"/api/v1/quizzes/{quiz_id}", json={"is_published": True}, headers=owner
    )

    attempt = await start(api_client, quiz_id, student)
    assert attempt["deadline_at"] is None
    assert attempt["seconds_remaining"] is None


# --- Progress and history --------------------------------------------------


async def test_passing_the_quiz_finishes_the_lesson(
    api_client: AsyncClient,
    db_session: AsyncSession,
    quiz: dict,
    lesson: dict,
    student_user: User,
    student: dict[str, str],
):
    """Same rule as an accepted code submission, in the same transaction."""
    attempt = await start(api_client, quiz["id"], student)
    await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [0, 1]},
        headers=student,
    )

    completed_at = await db_session.scalar(
        select(LessonProgress.completed_at)
        .join(Enrollment, Enrollment.id == LessonProgress.enrollment_id)
        .where(
            LessonProgress.lesson_id == uuid.UUID(lesson["id"]),
            Enrollment.user_id == student_user.id,
        )
    )
    assert completed_at is not None


async def test_failing_the_quiz_leaves_the_lesson_open(
    api_client: AsyncClient,
    db_session: AsyncSession,
    quiz: dict,
    lesson: dict,
    student_user: User,
    student: dict[str, str],
):
    attempt = await start(api_client, quiz["id"], student)
    await api_client.post(
        f"/api/v1/quiz-attempts/{attempt['id']}/submit",
        json={"answers": [1, 2]},
        headers=student,
    )

    rows = (
        await db_session.scalars(
            select(LessonProgress)
            .join(Enrollment, Enrollment.id == LessonProgress.enrollment_id)
            .where(
                LessonProgress.lesson_id == uuid.UUID(lesson["id"]),
                Enrollment.user_id == student_user.id,
            )
        )
    ).all()
    assert [row.completed_at for row in rows] in ([], [None])


async def test_the_history_lists_your_own_attempts_newest_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
    quiz: dict,
    student: dict[str, str],
):
    first = await start(api_client, quiz["id"], student)
    await api_client.post(
        f"/api/v1/quiz-attempts/{first['id']}/submit",
        json={"answers": [1, 2]},
        headers=student,
    )
    second = await start(api_client, quiz["id"], student)
    await api_client.post(
        f"/api/v1/quiz-attempts/{second['id']}/submit",
        json={"answers": [0, 1]},
        headers=student,
    )

    page = (
        await api_client.get(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=student)
    ).json()

    assert page["total"] == 2
    assert [row["id"] for row in page["items"]] == [second["id"], first["id"]]
    assert [row["passed"] for row in page["items"]] == [True, False]


# --- Who may do what -------------------------------------------------------


async def test_another_students_attempt_is_not_found(
    api_client: AsyncClient,
    db_session: AsyncSession,
    lesson: dict,
    quiz: dict,
    student: dict[str, str],
):
    """Not 403: "this exists but is not yours" is a fact about someone else."""
    other = await make_user(db_session, "student")
    db_session.add(Enrollment(user_id=other.id, course_id=uuid.UUID(lesson["course_id"])))
    await db_session.flush()
    theirs = await start(api_client, quiz["id"], await sign_in(api_client, other))

    response = await api_client.get(
        f"/api/v1/quiz-attempts/{theirs['id']}", headers=student
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ATTEMPT_NOT_FOUND"


async def test_signing_in_is_required_to_start(api_client: AsyncClient, quiz: dict):
    response = await api_client.post(f"/api/v1/quizzes/{quiz['id']}/attempts")
    assert response.status_code == 401


async def test_a_student_who_has_not_enrolled_cannot_start(
    api_client: AsyncClient, db_session: AsyncSession, quiz: dict
):
    outsider = await make_user(db_session, "student")
    headers = await sign_in(api_client, outsider)

    response = await api_client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers
    )
    assert response.status_code == 403


async def test_a_draft_quiz_is_not_open_to_students(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str], student: dict[str, str]
):
    created = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz", json={}, headers=owner
    )
    quiz_id = created.json()["id"]
    await add_question(api_client, quiz_id, owner, "1 + 1 = ?", ["1", "2"], 1)

    response = await api_client.post(
        f"/api/v1/quizzes/{quiz_id}/attempts", headers=student
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUIZ_NOT_PUBLISHED"


async def test_the_instructor_may_sit_their_own_draft(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str]
):
    """Previewing what students will see is how a generated quiz gets checked."""
    created = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/quiz", json={}, headers=owner
    )
    quiz_id = created.json()["id"]
    await add_question(api_client, quiz_id, owner, "1 + 1 = ?", ["1", "2"], 1)

    response = await api_client.post(
        f"/api/v1/quizzes/{quiz_id}/attempts", headers=owner
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["questions"]) == 1
    # Even for the author: an attempt is an attempt, and the model it comes
    # back in has no answer key on it.
    assert "correct_index" not in response.text


# --- What the database refuses on its own ---------------------------------


async def test_two_unfinished_attempts_are_refused_by_the_database(
    db_session: AsyncSession, quiz: dict, student_user: User
):
    """The backstop if two requests ever race past the service check."""
    for _ in range(2):
        db_session.add(
            QuizAttempt(
                quiz_id=uuid.UUID(quiz["id"]),
                user_id=student_user.id,
                started_at=datetime.now(UTC),
                time_limit_s=TIME_LIMIT_S,
            )
        )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_an_expired_attempt_cannot_carry_a_score(
    db_session: AsyncSession, quiz: dict, student_user: User
):
    """Running out of time is worth no marks, and nothing else.

    Nothing is saved while an attempt runs, so there is no partial answer a
    future endpoint could honestly award -- the table says so rather than
    trusting everyone who writes to it to remember.
    """
    db_session.add(
        QuizAttempt(
            quiz_id=uuid.UUID(quiz["id"]),
            user_id=student_user.id,
            started_at=datetime.now(UTC),
            submitted_at=datetime.now(UTC),
            answers=[0, 1],
            score=100,
            expired=True,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
