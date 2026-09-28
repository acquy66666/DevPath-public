"""XP and the daily streak.

Two rules carry this file. XP is paid **once per thing** -- a lesson finished
twice, a quiz passed twice or an exercise solved twice earns nothing the second
time -- and only to somebody **enrolled**, so an instructor trying their own
course earns nothing from it. A day counts towards the streak when the student
*did* something: finished a lesson, handed in a quiz, submitted code. Watching
is not enough, and neither is a trial run.

The streak's arithmetic is tested against explicit days rather than the clock:
nobody waits until tomorrow to find out whether tomorrow works.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    Category,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Quiz,
    QuizQuestion,
    Streak,
    TestCase,
    User,
    XpEvent,
)
from app.services import gamification
from app.services import grading as grading_service

PASSWORD = "mật-khẩu-đủ-dài"
ME = "/api/v1/users/me"

MONDAY = date(2026, 9, 21)


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


class CourseFixture:
    """A published course with one lesson of each kind that can pay XP."""

    course: Course
    video: Lesson
    quiz_lesson: Lesson
    quiz: Quiz
    code_lesson: Lesson
    exercise: CodeExercise


async def make_course(session: AsyncSession, owner: User) -> CourseFixture:
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title="Lập trình Python cơ bản",
        slug=f"python-co-ban-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    video = Lesson(section_id=section.id, title="Biến và kiểu dữ liệu", type="video", position=0)
    quiz_lesson = Lesson(section_id=section.id, title="Kiểm tra chương 1", type="quiz", position=1)
    code_lesson = Lesson(
        section_id=section.id, title="Bài tập: tổng hai số", type="code_exercise", position=2
    )
    session.add_all([video, quiz_lesson, code_lesson])
    await session.flush()

    quiz = Quiz(lesson_id=quiz_lesson.id, pass_score=50, is_published=True)
    exercise = CodeExercise(
        lesson_id=code_lesson.id,
        statement_md="Đọc hai số, in ra tổng.",
        language="python",
        time_limit_ms=2000,
        memory_limit_mb=128,
    )
    session.add_all([quiz, exercise])
    await session.flush()

    session.add_all(
        [
            QuizQuestion(
                quiz_id=quiz.id,
                question="1 + 1 = ?",
                options=["1", "2"],
                correct_index=1,
                position=0,
            ),
            QuizQuestion(
                quiz_id=quiz.id,
                question="2 + 2 = ?",
                options=["4", "5"],
                correct_index=0,
                position=1,
            ),
            TestCase(
                exercise_id=exercise.id,
                input="1 2\n",
                expected_output="3\n",
                is_hidden=False,
                position=0,
            ),
            TestCase(
                exercise_id=exercise.id,
                input="2 2\n",
                expected_output="4\n",
                is_hidden=True,
                position=1,
            ),
        ]
    )
    await session.flush()

    fixture = CourseFixture()
    fixture.course = course
    fixture.video = video
    fixture.quiz_lesson = quiz_lesson
    fixture.quiz = quiz
    fixture.code_lesson = code_lesson
    fixture.exercise = exercise
    return fixture


@pytest.fixture(autouse=True)
def queued(monkeypatch: pytest.MonkeyPatch) -> list:
    """Submissions go nowhere: grading is the worker's test file's business."""
    ids: list = []
    monkeypatch.setattr(grading_service, "enqueue_grading", ids.append)
    return ids


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def course(db_session: AsyncSession, owner: User) -> CourseFixture:
    return await make_course(db_session, owner)


@pytest.fixture
async def student(db_session: AsyncSession, course: CourseFixture) -> User:
    user = await make_user(db_session, "student")
    db_session.add(Enrollment(user_id=user.id, course_id=course.course.id))
    await db_session.flush()
    return user


async def xp_of(session: AsyncSession, user: User) -> list[tuple[str, int]]:
    rows = await session.execute(
        select(XpEvent.reason, XpEvent.amount)
        .where(XpEvent.user_id == user.id)
        .order_by(XpEvent.reason)
    )
    return [tuple(row) for row in rows]


async def streak_of(session: AsyncSession, user: User) -> Streak | None:
    return await session.scalar(select(Streak).where(Streak.user_id == user.id))


async def complete(
    client: AsyncClient, lesson: Lesson, headers: dict, completed: bool | None = True
):
    body: dict = {"last_position_s": 30}
    if completed is not None:
        body["completed"] = completed
    response = await client.put(f"/api/v1/lessons/{lesson.id}/progress", json=body, headers=headers)
    assert response.status_code == 200, response.text


async def sit_quiz(client: AsyncClient, quiz: Quiz, headers: dict, answers: list[int]) -> dict:
    attempt = await client.post(f"/api/v1/quizzes/{quiz.id}/attempts", headers=headers)
    assert attempt.status_code == 201, attempt.text
    submitted = await client.post(
        f"/api/v1/quiz-attempts/{attempt.json()['id']}/submit",
        json={"answers": answers},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


# --- The ledger: once per thing --------------------------------------------


async def test_the_first_award_is_recorded_at_the_reasons_rate(
    db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    paid = await gamification.award(
        db_session, user_id=student.id, reason="lesson_completed", ref_id=course.video.id
    )

    assert paid is True
    assert await xp_of(db_session, student) == [
        ("lesson_completed", gamification.XP_AMOUNTS["lesson_completed"])
    ]


async def test_the_same_thing_never_pays_twice(
    db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    for _ in range(3):
        await gamification.award(
            db_session, user_id=student.id, reason="lesson_completed", ref_id=course.video.id
        )

    again = await gamification.award(
        db_session, user_id=student.id, reason="lesson_completed", ref_id=course.video.id
    )

    assert again is False
    assert len(await xp_of(db_session, student)) == 1


async def test_two_students_finishing_the_same_lesson_both_earn(
    db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    other = await make_user(db_session)

    for user in (student, other):
        await gamification.award(
            db_session, user_id=user.id, reason="lesson_completed", ref_id=course.video.id
        )

    assert len(await xp_of(db_session, student)) == 1
    assert len(await xp_of(db_session, other)) == 1


async def test_a_reason_cannot_point_at_the_wrong_kind_of_thing(
    db_session: AsyncSession, student: User
) -> None:
    """The service never writes this pair; the constraint is there for code that
    writes rows some other way -- a backfill script, a hand-typed fix."""
    db_session.add(
        XpEvent(
            user_id=student.id,
            amount=10,
            reason="quiz_passed",
            ref_type="lesson",
            ref_id=uuid.uuid4(),
        )
    )
    with pytest.raises(IntegrityError, match="ck_xp_events_reason_ref"):
        await db_session.flush()


# --- The streak's arithmetic ------------------------------------------------


async def test_the_first_active_day_starts_a_streak_of_one(
    db_session: AsyncSession, student: User
) -> None:
    await gamification.record_active_day(db_session, user_id=student.id, day=MONDAY)

    streak = await streak_of(db_session, student)
    assert (streak.current_streak, streak.longest_streak, streak.last_active_date) == (1, 1, MONDAY)


async def test_a_second_activity_on_the_same_day_is_the_same_day(
    db_session: AsyncSession, student: User
) -> None:
    for _ in range(3):
        await gamification.record_active_day(db_session, user_id=student.id, day=MONDAY)

    streak = await streak_of(db_session, student)
    assert (streak.current_streak, streak.longest_streak) == (1, 1)


async def test_consecutive_days_grow_the_streak(db_session: AsyncSession, student: User) -> None:
    for offset in range(4):
        await gamification.record_active_day(
            db_session, user_id=student.id, day=MONDAY + timedelta(days=offset)
        )

    streak = await streak_of(db_session, student)
    assert (streak.current_streak, streak.longest_streak) == (4, 4)


async def test_a_missed_day_starts_again_but_the_best_is_kept(
    db_session: AsyncSession, student: User
) -> None:
    for offset in (0, 1, 2, 4):  # Thursday is missing.
        await gamification.record_active_day(
            db_session, user_id=student.id, day=MONDAY + timedelta(days=offset)
        )

    streak = await streak_of(db_session, student)
    assert (streak.current_streak, streak.longest_streak) == (1, 3)
    assert streak.last_active_date == MONDAY + timedelta(days=4)


async def test_an_earlier_day_arriving_late_changes_nothing(
    db_session: AsyncSession, student: User
) -> None:
    """A write stamped with yesterday (a request that straddled midnight) must
    not drag the streak backwards."""
    await gamification.record_active_day(db_session, user_id=student.id, day=MONDAY)
    await gamification.record_active_day(
        db_session, user_id=student.id, day=MONDAY + timedelta(days=1)
    )

    await gamification.record_active_day(db_session, user_id=student.id, day=MONDAY)

    streak = await streak_of(db_session, student)
    assert (streak.current_streak, streak.last_active_date) == (2, MONDAY + timedelta(days=1))


async def test_a_streak_reads_as_alive_until_a_whole_day_is_missed(
    db_session: AsyncSession, student: User
) -> None:
    """Nothing runs at midnight to break a streak: whoever reads it decides.
    Yesterday's streak is still yours today -- you have until tonight."""
    await gamification.record_active_day(db_session, user_id=student.id, day=MONDAY)
    await gamification.record_active_day(
        db_session, user_id=student.id, day=MONDAY + timedelta(days=1)
    )

    same_day = await gamification.get_summary(
        db_session, student.id, today=MONDAY + timedelta(days=1)
    )
    next_day = await gamification.get_summary(
        db_session, student.id, today=MONDAY + timedelta(days=2)
    )
    too_late = await gamification.get_summary(
        db_session, student.id, today=MONDAY + timedelta(days=3)
    )

    assert (same_day.current_streak, same_day.active_today) == (2, True)
    assert (next_day.current_streak, next_day.active_today) == (2, False)
    assert (too_late.current_streak, too_late.active_today) == (0, False)
    assert too_late.longest_streak == 2


@pytest.mark.parametrize(
    ("instant", "day"),
    [
        # 23:59 in Hà Nội is still the 27th...
        (datetime(2026, 9, 27, 16, 59, tzinfo=UTC), date(2026, 9, 27)),
        # ...and ten past midnight there is the 28th, while UTC is still on the 27th.
        (datetime(2026, 9, 27, 17, 10, tzinfo=UTC), date(2026, 9, 28)),
    ],
)
def test_a_day_is_a_day_in_vietnam(instant: datetime, day: date) -> None:
    assert gamification.today_in_vietnam(instant) == day


# --- Where XP and active days come from ------------------------------------


async def test_finishing_a_lesson_pays_once_and_counts_the_day(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    headers = await sign_in(api_client, student)

    await complete(api_client, course.video, headers)

    assert await xp_of(db_session, student) == [("lesson_completed", 10)]
    streak = await streak_of(db_session, student)
    assert streak is not None
    assert streak.last_active_date == gamification.today_in_vietnam()


async def test_unticking_and_ticking_a_lesson_again_pays_nothing_more(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    """Otherwise the tick box is an XP tap."""
    headers = await sign_in(api_client, student)

    await complete(api_client, course.video, headers, True)
    await complete(api_client, course.video, headers, False)
    await complete(api_client, course.video, headers, True)

    assert await xp_of(db_session, student) == [("lesson_completed", 10)]


async def test_watching_without_finishing_earns_nothing(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    """The player's heartbeat is not studying something through, and a video
    left playing in a background tab would otherwise keep a streak alive."""
    headers = await sign_in(api_client, student)

    await complete(api_client, course.video, headers, completed=None)

    assert await xp_of(db_session, student) == []
    assert await streak_of(db_session, student) is None


async def test_passing_a_quiz_pays_for_the_quiz_and_its_lesson(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    headers = await sign_in(api_client, student)

    result = await sit_quiz(api_client, course.quiz, headers, [1, 0])

    assert result["passed"] is True
    assert await xp_of(db_session, student) == [("lesson_completed", 10), ("quiz_passed", 20)]
    assert await streak_of(db_session, student) is not None


async def test_passing_a_quiz_again_pays_nothing_more(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    headers = await sign_in(api_client, student)

    await sit_quiz(api_client, course.quiz, headers, [1, 0])
    await sit_quiz(api_client, course.quiz, headers, [1, 0])

    assert len(await xp_of(db_session, student)) == 2


async def test_failing_a_quiz_earns_nothing_but_still_counts_the_day(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    """Handing in a paper is studying, whatever it scored."""
    headers = await sign_in(api_client, student)

    result = await sit_quiz(api_client, course.quiz, headers, [0, 1])

    assert result["passed"] is False
    assert await xp_of(db_session, student) == []
    assert await streak_of(db_session, student) is not None


async def test_submitting_code_counts_the_day(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    """Counted when handed in rather than when graded: the student worked on
    the day they pressed the button, not the day the queue got round to it.
    The XP itself waits for the verdict -- see the worker's tests."""
    headers = await sign_in(api_client, student)

    response = await api_client.post(
        f"/api/v1/code-exercises/{course.exercise.id}/submissions",
        json={"code": "print(3)"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert await streak_of(db_session, student) is not None
    assert await xp_of(db_session, student) == []


async def test_a_trial_run_does_not_count_the_day(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    """A trial run is a draft; "Nộp bài" is the act that counts."""
    headers = await sign_in(api_client, student)

    response = await api_client.post(
        f"/api/v1/code-exercises/{course.exercise.id}/trial-runs",
        json={"code": "print(3)"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert await streak_of(db_session, student) is None


async def test_an_instructor_trying_their_own_course_earns_nothing(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, course: CourseFixture
) -> None:
    """No enrolment, no XP and no streak -- the author of a course must not
    climb the leaderboard by rehearsing it."""
    headers = await sign_in(api_client, owner)

    await sit_quiz(api_client, course.quiz, headers, [1, 0])
    await api_client.post(
        f"/api/v1/code-exercises/{course.exercise.id}/submissions",
        json={"code": "print(3)"},
        headers=headers,
    )

    assert await xp_of(db_session, owner) == []
    assert await streak_of(db_session, owner) is None


# --- Reading it back ---------------------------------------------------------


async def test_the_summary_needs_a_sign_in(api_client: AsyncClient) -> None:
    response = await api_client.get(f"{ME}/gamification")

    assert response.status_code == 401


async def test_somebody_who_has_done_nothing_yet_reads_zeros(
    api_client: AsyncClient, student: User
) -> None:
    headers = await sign_in(api_client, student)

    response = await api_client.get(f"{ME}/gamification", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "xp_total": 0,
        "current_streak": 0,
        "longest_streak": 0,
        "last_active_date": None,
        "active_today": False,
    }


async def test_the_summary_adds_up_what_was_earned_today(
    api_client: AsyncClient, student: User, course: CourseFixture
) -> None:
    headers = await sign_in(api_client, student)
    await complete(api_client, course.video, headers)
    await sit_quiz(api_client, course.quiz, headers, [1, 0])

    body = (await api_client.get(f"{ME}/gamification", headers=headers)).json()

    assert body["xp_total"] == 10 + 10 + 20
    assert body["current_streak"] == 1
    assert body["active_today"] is True
    assert body["last_active_date"] == gamification.today_in_vietnam().isoformat()


async def test_the_history_is_yours_newest_first_and_names_the_lesson(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    headers = await sign_in(api_client, student)
    await complete(api_client, course.video, headers)
    await sit_quiz(api_client, course.quiz, headers, [1, 0])
    # Somebody else's XP must not appear.
    other = await make_user(db_session)
    await gamification.award(
        db_session, user_id=other.id, reason="lesson_completed", ref_id=course.video.id
    )
    # Pin the order: rows written in one test transaction share `now()`.
    hour_of = {course.video.id: 0, course.quiz_lesson.id: 1, course.quiz.id: 2}
    rows = (await db_session.scalars(select(XpEvent).where(XpEvent.user_id == student.id))).all()
    for row in rows:
        row.created_at = datetime(2026, 9, 21, hour_of[row.ref_id], tzinfo=UTC)
    await db_session.flush()

    response = await api_client.get(f"{ME}/xp-events", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [(item["reason"], item["amount"]) for item in body["items"]] == [
        ("quiz_passed", 20),
        ("lesson_completed", 10),
        ("lesson_completed", 10),
    ]
    assert body["items"][0]["lesson"]["title"] == "Kiểm tra chương 1"
    assert body["items"][2]["lesson"]["title"] == "Biến và kiểu dữ liệu"
    assert body["items"][0]["course"]["slug"] == course.course.slug


async def test_the_history_survives_the_lesson_being_deleted(
    api_client: AsyncClient, db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    """The XP stays -- the student did finish it -- and the history says the
    lesson is gone rather than failing to draw."""
    headers = await sign_in(api_client, student)
    await complete(api_client, course.video, headers)
    await db_session.delete(course.video)
    await db_session.flush()

    body = (await api_client.get(f"{ME}/xp-events", headers=headers)).json()
    summary = (await api_client.get(f"{ME}/gamification", headers=headers)).json()

    assert [(item["reason"], item["lesson"], item["course"]) for item in body["items"]] == [
        ("lesson_completed", None, None)
    ]
    assert summary["xp_total"] == 10


async def test_the_history_is_paginated(
    api_client: AsyncClient, db_session: AsyncSession, student: User
) -> None:
    for _ in range(3):
        await gamification.award(
            db_session, user_id=student.id, reason="lesson_completed", ref_id=uuid.uuid4()
        )
    headers = await sign_in(api_client, student)

    page = (await api_client.get(f"{ME}/xp-events?page=2&page_size=2", headers=headers)).json()
    too_big = await api_client.get(f"{ME}/xp-events?page_size=101", headers=headers)

    assert (page["total"], page["page"], page["page_size"], len(page["items"])) == (3, 2, 2, 1)
    assert too_big.status_code == 422


async def test_xp_total_is_a_sum_over_the_ledger(
    db_session: AsyncSession, student: User, course: CourseFixture
) -> None:
    """No running total is stored anywhere to drift from the rows."""
    await gamification.award(
        db_session, user_id=student.id, reason="lesson_completed", ref_id=course.video.id
    )
    await gamification.award(
        db_session, user_id=student.id, reason="exercise_solved", ref_id=course.exercise.id
    )

    summary = await gamification.get_summary(db_session, student.id)
    total = await db_session.scalar(
        select(func.sum(XpEvent.amount)).where(XpEvent.user_id == student.id)
    )

    assert summary.xp_total == total == 10 + 30
