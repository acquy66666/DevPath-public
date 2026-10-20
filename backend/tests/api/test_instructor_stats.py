"""The instructor's dashboard: learners and learning, and no money.

Since 20/10/2026 an instructor sees their courses and their learners, never a
figure with money in it -- that is the admin's (`test_finance.py`). The tests
pin down both halves:

* **no money** anywhere an instructor can reach: no field with a money-shaped
  name in any response, money-shaped tier criteria reported as met / not met
  only, and no money column or "₫" in the Excel export;
* what each learning figure **means**: a new student is somebody whose first
  course with this instructor began in the window; an active learner left a
  trace on these courses in it (the instructor's own traces never count);
  completion and progress are over every enrolment, a finished one counting
  as every lesson done; first-try pass is the first submitted attempt; solved
  is an AC on a graded submission; a question is answered when the instructor
  replies.

Rows are written straight into the tables with their times spelled out,
because the thing under test is how time is cut into buckets.
"""

import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Cart,
    CartItem,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonProgress,
    Note,
    Order,
    OrderItem,
    QaReply,
    QaThread,
    Quiz,
    QuizAttempt,
    Review,
    Submission,
    User,
    VideoAsset,
    Wishlist,
)
from app.services.vnpay import VIETNAM
from tests.api.test_commerce import make_course, make_user, sign_in

OVERVIEW = "/api/v1/instructor/stats/overview"
INSIGHTS = "/api/v1/instructor/stats/insights"
COURSES = "/api/v1/instructor/stats/courses"
EXPORT = "/api/v1/instructor/stats/export.xlsx"
TIER = "/api/v1/instructor/tier"

#: Field names that would put money on an instructor's screen.
MONEY_WORDS = ("revenue", "sales", "price", "amount", "paid", "discount", "commission", "payout")


def today() -> date:
    return datetime.now(VIETNAM).date()


def at(day: date, hour: int = 12, minute: int = 0) -> datetime:
    """A moment on a Vietnamese calendar day."""
    return datetime.combine(day, time(hour, minute), VIETNAM)


def first_of_month(day: date, months_back: int = 0) -> date:
    month = day.year * 12 + day.month - 1 - months_back
    return date(month // 12, month % 12 + 1, 1)


async def sell(
    session: AsyncSession,
    buyer: User,
    lines: list[tuple[Course, str, str]],
    *,
    paid_at: datetime | None,
    status: str = "paid",
    share_rate: str = "0.5000",
    provider: str = "vnpay",
) -> Order:
    """An order of (course, unit price, line discount), in the given state --
    paid lines frozen at `share_rate`, as `orders._deliver` would."""
    subtotal = sum((Decimal(price) for _, price, _ in lines), Decimal(0))
    discount = sum((Decimal(off) for _, _, off in lines), Decimal(0))
    order = Order(
        user_id=buyer.id,
        code=f"DP{secrets.token_hex(6).upper()}",
        subtotal=subtotal,
        discount=discount,
        total=subtotal - discount,
        status=status,
        payment_provider=provider,
        paid_at=paid_at if status == "paid" else None,
        provider_txn_id=secrets.token_hex(8) if status == "paid" else None,
    )
    session.add(order)
    await session.flush()
    session.add_all(
        OrderItem(
            order_id=order.id,
            course_id=course.id,
            unit_price=Decimal(price),
            discount=Decimal(off),
            instructor_share_rate=Decimal(share_rate) if status == "paid" else None,
        )
        for course, price, off in lines
    )
    await session.flush()
    return order


async def enrol(
    session: AsyncSession,
    user: User,
    course: Course,
    *,
    when: datetime,
    completed: bool = False,
    source: str = "free",
) -> Enrollment:
    enrollment = Enrollment(
        user_id=user.id,
        course_id=course.id,
        source=source,
        created_at=when,
        completed_at=when if completed else None,
    )
    session.add(enrollment)
    await session.flush()
    return enrollment


async def add_lessons(
    session: AsyncSession, course: Course, count: int, lesson_type: str = "article"
) -> list[Lesson]:
    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()
    lessons = [
        Lesson(section_id=section.id, title=f"Bài {i + 1}", type=lesson_type, position=i)
        for i in range(count)
    ]
    session.add_all(lessons)
    await session.flush()
    return lessons


async def finish(session: AsyncSession, enrollment: Enrollment, lessons: list[Lesson]) -> None:
    session.add_all(
        LessonProgress(
            enrollment_id=enrollment.id,
            lesson_id=lesson.id,
            completed_at=enrollment.created_at,
        )
        for lesson in lessons
    )
    await session.flush()


async def touch(
    session: AsyncSession, enrollment: Enrollment, lesson: Lesson, when: datetime, **fields
) -> LessonProgress:
    progress = LessonProgress(
        enrollment_id=enrollment.id,
        lesson_id=lesson.id,
        created_at=when,
        updated_at=when,
        **fields,
    )
    session.add(progress)
    await session.flush()
    return progress


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def buyer(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student")


async def get(client: AsyncClient, path: str, headers: dict[str, str], **params) -> dict:
    response = await client.get(path, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def overview(client: AsyncClient, headers: dict[str, str], period: str = "30d") -> dict:
    return await get(client, OVERVIEW, headers, period=period)


async def insights(client: AsyncClient, headers: dict[str, str], period: str = "30d") -> dict:
    return await get(client, INSIGHTS, headers, period=period)


async def course_rows(client: AsyncClient, headers: dict[str, str], **params) -> dict:
    return await get(client, COURSES, headers, **params)


def point(body: dict, day: date) -> dict:
    return next(p for p in body["series"] if p["bucket"] == day.isoformat())


def money_fields(body, path: str = "") -> list[str]:
    found = []
    if isinstance(body, dict):
        for key, value in body.items():
            if any(word in key for word in MONEY_WORDS):
                found.append(f"{path}.{key}")
            found += money_fields(value, f"{path}.{key}")
    elif isinstance(body, list):
        for item in body:
            found += money_fields(item, f"{path}[]")
    return found


# --- Who may ask -----------------------------------------------------------


@pytest.mark.parametrize("path", [OVERVIEW, INSIGHTS, COURSES, EXPORT, TIER])
async def test_a_signed_out_visitor_is_told_to_sign_in(api_client: AsyncClient, path: str) -> None:
    response = await api_client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize("path", [OVERVIEW, INSIGHTS, COURSES, EXPORT, TIER])
async def test_a_student_has_no_dashboard(api_client: AsyncClient, buyer: User, path: str) -> None:
    response = await api_client.get(path, headers=await sign_in(api_client, buyer))

    assert response.status_code == 403


@pytest.mark.parametrize("path", [OVERVIEW, INSIGHTS, COURSES, EXPORT])
async def test_a_period_that_is_not_on_the_menu_is_refused(
    api_client: AsyncClient, owner: User, path: str
) -> None:
    response = await api_client.get(
        path, params={"period": "45d"}, headers=await sign_in(api_client, owner)
    )

    assert response.status_code == 422


async def test_another_instructors_course_has_no_lesson_breakdown_for_me(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    theirs = await make_course(db_session, await make_user(db_session, "instructor"))

    response = await api_client.get(
        f"{COURSES}/{theirs.id}/lessons", headers=await sign_in(api_client, owner)
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


# --- No money ----------------------------------------------------------------


async def test_nothing_an_instructor_reads_carries_money(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    """Courses that sold, with coupons, and every instructor endpoint read
    back: no money-shaped field anywhere, and the tier's money criteria come
    back as met / not met with no value and no threshold."""
    course = await make_course(db_session, owner, price="400000")
    await add_lessons(db_session, course, 2)
    await sell(db_session, buyer, [(course, "400000", "120000")], paid_at=at(today()))
    await enrol(db_session, buyer, course, when=at(today()), source="purchase")
    headers = await sign_in(api_client, owner)

    bodies = [
        await overview(api_client, headers, "12m"),
        await insights(api_client, headers),
        await course_rows(api_client, headers),
        await get(api_client, f"{COURSES}/{course.id}/lessons", headers),
    ]
    for body in bodies:
        assert money_fields(body) == []
        assert "400000" not in str(body) and "280000" not in str(body)

    tier = await get(api_client, TIER, headers)
    hidden = {c["key"]: c for c in tier["next"]["criteria"] if c["value"] is None}
    assert set(hidden) == {"paid_students", "revenue_12m"}
    assert all(c["threshold"] is None for c in hidden.values())
    assert "400000" not in str(tier) and "5000000" not in str(tier)


async def test_the_export_has_no_money_either(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    course = await make_course(db_session, owner, price="400000", title='=HYPERLINK("x")')
    await sell(db_session, buyer, [(course, "400000", "0")], paid_at=at(today()))
    await enrol(db_session, buyer, course, when=at(today()), source="purchase")

    response = await api_client.get(
        EXPORT, params={"period": "30d"}, headers=await sign_in(api_client, owner)
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    book = load_workbook(BytesIO(response.content))
    assert book.sheetnames == [
        "Tổng quan",
        "Từ trước tới nay",
        "Tỉ lệ",
        "Theo thời gian",
        "Kết quả học tập",
        "Theo khóa học",
    ]
    text = []
    for sheet in book.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is not None:
                    text.append(str(cell.value))
                    assert "₫" not in (cell.number_format or "")
    joined = " ".join(text).lower()
    for word in ("doanh thu", "giá bán", "giá niêm yết", "tiền", "₫", "400000", "hoa hồng"):
        assert word not in joined
    # A title that looks like a formula is written as text, never run.
    course_sheet = book["Theo khóa học"]
    titles = [row[0].value for row in course_sheet.iter_rows() if row[0].value]
    assert '=HYPERLINK("x")' in titles
    assert all(
        cell.data_type == "s"
        for row in course_sheet.iter_rows()
        for cell in row
        if isinstance(cell.value, str)
    )


# --- Students ----------------------------------------------------------------


async def test_a_student_new_to_me_is_counted_once(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Two of my courses on the same afternoon: two enrolments, one new
    student. Somebody who has been with me since last quarter and starts
    another course today is an enrolment, not a new student."""
    first = await make_course(db_session, owner)
    second = await make_course(db_session, owner)
    newcomer = await make_user(db_session, "student")
    regular = await make_user(db_session, "student")
    yesterday = today() - timedelta(days=1)
    await enrol(db_session, newcomer, first, when=at(yesterday, 14))
    await enrol(db_session, newcomer, second, when=at(yesterday, 15))
    await enrol(db_session, regular, first, when=at(today() - timedelta(days=90)))
    await enrol(db_session, regular, second, when=at(yesterday))

    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"]["enrollments"] == 3
    assert body["current"]["new_students"] == 1
    assert point(body, yesterday)["new_students"] == 1
    assert body["students_total"] == 2
    assert body["enrollments_total"] == 4


async def test_an_enrolment_just_after_midnight_belongs_to_the_new_day(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    """00:10 in Hà Nội is 17:10 the previous day in UTC."""
    course = await make_course(db_session, owner)
    day = today() - timedelta(days=2)
    await enrol(db_session, buyer, course, when=at(day, 0, 10))

    body = await overview(api_client, await sign_in(api_client, owner), "7d")

    assert point(body, day)["enrollments"] == 1
    assert point(body, day - timedelta(days=1))["enrollments"] == 0


async def test_somebody_elses_students_are_not_mine(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    theirs = await make_course(db_session, await make_user(db_session, "instructor"))
    await enrol(db_session, buyer, theirs, when=at(today()))

    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"]["enrollments"] == 0
    assert body["students_total"] == 0
    assert body["completion_rate"] is None


async def test_active_learners_are_distinct_and_never_the_instructor(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Three learners leave traces of three kinds -- one of them twice -- and
    the instructor tries their own quiz. Three active learners; the instructor
    is not one of them."""
    course = await make_course(db_session, owner)
    [lesson] = await add_lessons(db_session, course, 1, "quiz")
    quiz = Quiz(lesson_id=lesson.id, pass_score=70, is_published=True)
    db_session.add(quiz)
    await db_session.flush()
    yesterday = at(today() - timedelta(days=1))

    reader, quizzer, writer = [await make_user(db_session) for _ in range(3)]
    long_ago = at(today() - timedelta(days=60))
    reading = await enrol(db_session, reader, course, when=long_ago)
    for learner in (quizzer, writer):
        await enrol(db_session, learner, course, when=long_ago)
    await touch(db_session, reading, lesson, yesterday)
    for who in (quizzer, owner):
        db_session.add(
            QuizAttempt(
                quiz_id=quiz.id,
                user_id=who.id,
                started_at=yesterday,
                submitted_at=yesterday,
                score=80,
                answers=[0],
            )
        )
    for content in ("ghi chú", "ghi chú 2"):
        db_session.add(
            Note(user_id=writer.id, lesson_id=lesson.id, content=content, created_at=yesterday)
        )
    await db_session.flush()

    body = await overview(api_client, await sign_in(api_client, owner), "7d")

    assert body["current"]["active_learners"] == 3
    assert point(body, today() - timedelta(days=1))["active_learners"] == 3
    assert body["previous"]["active_learners"] == 0


async def test_lessons_and_courses_completed_in_the_window(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    lessons = await add_lessons(db_session, course, 2)
    yesterday = at(today() - timedelta(days=1))
    learner = await make_user(db_session)
    enrolment = await enrol(db_session, learner, course, when=yesterday, completed=True)
    await finish(db_session, enrolment, lessons)

    body = await overview(api_client, await sign_in(api_client, owner), "7d")

    assert body["current"]["lessons_completed"] == 2
    assert body["current"]["completions"] == 1
    assert body["certificates_total"] == 0


# --- Per course --------------------------------------------------------------


async def test_completion_progress_and_start_per_course(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Four students, two lessons: one finished, one halfway, two not started.
    One in four finished (0.25); three lessons done of eight (0.375); two of
    four started (0.5)."""
    course = await make_course(db_session, owner)
    lessons = await add_lessons(db_session, course, 2)
    when = at(today() - timedelta(days=3))
    done = await enrol(db_session, await make_user(db_session), course, when=when, completed=True)
    await finish(db_session, done, lessons)
    halfway = await enrol(db_session, await make_user(db_session), course, when=when)
    await finish(db_session, halfway, lessons[:1])
    for _ in range(2):
        await enrol(db_session, await make_user(db_session), course, when=when)

    body = await course_rows(api_client, await sign_in(api_client, owner))

    [row] = body["items"]
    assert row["course"]["id"] == str(course.id)
    assert row["students"] == 4
    assert row["new_enrollments"] == 4
    assert row["completed"] == 1
    assert row["lessons_count"] == 2
    assert row["completion_rate"] == 0.25
    assert row["avg_progress"] == 0.375
    assert row["started_rate"] == 0.5


async def test_a_finished_enrolment_counts_as_every_lesson_done(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """`completed_at` is the authority on "finished": a course that grew a
    lesson afterwards does not unfinish anybody, and progress never reads
    lower than the share who completed."""
    course = await make_course(db_session, owner)
    lessons = await add_lessons(db_session, course, 2)
    when = at(today() - timedelta(days=3))
    finished = await enrol(
        db_session, await make_user(db_session), course, when=when, completed=True
    )
    await finish(db_session, finished, lessons[:1])
    halfway = await enrol(db_session, await make_user(db_session), course, when=when)
    await finish(db_session, halfway, lessons[:1])

    body = await course_rows(api_client, await sign_in(api_client, owner))

    [row] = body["items"]
    assert row["completion_rate"] == 0.5
    assert row["avg_progress"] == 0.75


async def test_a_course_nobody_has_joined_has_no_rates_rather_than_zero(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    await make_course(db_session, owner)

    body = await course_rows(api_client, await sign_in(api_client, owner))

    [row] = body["items"]
    assert row["students"] == 0
    assert row["completion_rate"] is None
    assert row["avg_progress"] is None
    assert row["started_rate"] is None
    assert row["quiz_first_try_pass_rate"] is None


async def test_only_my_courses_are_listed_most_students_first_and_paged(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    quiet = await make_course(db_session, owner, title="Ít người")
    busy = await make_course(db_session, owner, title="Đông người")
    await make_course(db_session, owner)
    await make_course(db_session, await make_user(db_session, "instructor"))
    for _ in range(2):
        await enrol(db_session, await make_user(db_session), busy, when=at(today()))
    await enrol(db_session, await make_user(db_session), quiet, when=at(today()))

    body = await course_rows(api_client, await sign_in(api_client, owner), page_size=2)

    assert body["total"] == 3
    assert [row["course"]["id"] for row in body["items"]] == [str(busy.id), str(quiet.id)]


async def test_a_removed_course_stays_while_it_still_has_students(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    kept = await make_course(db_session, owner)
    gone = await make_course(db_session, owner)
    await enrol(db_session, buyer, kept, when=at(today()))
    for course in (kept, gone):
        course.deleted_at = datetime.now(VIETNAM)
    await db_session.flush()

    body = await course_rows(api_client, await sign_in(api_client, owner))

    assert [row["course"]["id"] for row in body["items"]] == [str(kept.id)]
    assert body["items"][0]["course"]["is_deleted"] is True


async def test_overall_rates_are_over_every_enrolment(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    first = await make_course(db_session, owner)
    second = await make_course(db_session, owner)
    when = at(today() - timedelta(days=100))
    await enrol(db_session, await make_user(db_session), first, when=when, completed=True)
    for _ in range(3):
        await enrol(db_session, await make_user(db_session), second, when=when)

    body = await overview(api_client, await sign_in(api_client, owner))

    # All-time, not the period: nobody joined in the last 30 days.
    assert body["current"]["enrollments"] == 0
    assert body["completion_rate"] == 0.25
    assert body["courses_total"] == 2
    assert body["courses_published"] == 2


async def test_an_instructor_with_nothing_yet_gets_an_empty_dashboard(
    api_client: AsyncClient, owner: User
) -> None:
    body = await overview(api_client, await sign_in(api_client, owner))

    assert body["current"] == {
        "enrollments": 0,
        "new_students": 0,
        "active_learners": 0,
        "lessons_completed": 0,
        "completions": 0,
        "reviews": 0,
        "review_avg": None,
        "questions": 0,
        "wishlist_adds": 0,
    }
    assert body["courses_total"] == 0
    assert len(body["series"]) == 30


async def test_a_year_is_counted_in_months(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    course = await make_course(db_session, owner)
    await enrol(db_session, buyer, course, when=at(first_of_month(today(), 3)))

    body = await overview(api_client, await sign_in(api_client, owner), "12m")

    assert body["granularity"] == "month"
    assert [p["bucket"] for p in body["series"]] == [
        first_of_month(today(), back).isoformat() for back in range(11, -1, -1)
    ]
    assert point(body, first_of_month(today(), 3))["enrollments"] == 1


# --- Insights ----------------------------------------------------------------


async def test_quiz_first_try_is_the_first_attempt_submitted(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """One learner fails then passes, another passes at once: half passed at
    the first try. Three attempts, a median of 80, one ran out of time."""
    course = await make_course(db_session, owner)
    [lesson] = await add_lessons(db_session, course, 1, "quiz")
    quiz = Quiz(lesson_id=lesson.id, pass_score=70, is_published=True)
    db_session.add(quiz)
    await db_session.flush()
    slow, quick = await make_user(db_session), await make_user(db_session)
    base = at(today() - timedelta(days=2))
    for who, score, offset, expired in (
        (slow, 0, 0, True),
        (slow, 90, 1, False),
        (quick, 80, 0, False),
    ):
        moment = base + timedelta(hours=offset)
        db_session.add(
            QuizAttempt(
                quiz_id=quiz.id,
                user_id=who.id,
                started_at=moment,
                submitted_at=moment,
                score=score,
                answers=[] if expired else [0],
                expired=expired,
            )
        )
    await db_session.flush()

    body = await insights(api_client, await sign_in(api_client, owner))

    assert body["quiz"]["attempts"] == 3
    assert body["quiz"]["learners"] == 2
    assert body["quiz"]["first_try_pass_rate"] == 0.5
    assert body["quiz"]["median_score"] == 80.0
    assert body["quiz"]["expired_rate"] == round(1 / 3, 4)


async def test_code_solved_is_an_ac_on_a_graded_submission(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """A learner gets WA, WA, then AC: three tries to AC. Another only ever
    gets AC on a *trial* run, which grades nothing: not solved, not counted."""
    course = await make_course(db_session, owner)
    [lesson] = await add_lessons(db_session, course, 1, "code_exercise")
    exercise = CodeExercise(lesson_id=lesson.id, statement_md="In ra 1")
    db_session.add(exercise)
    await db_session.flush()
    solver, tryer = await make_user(db_session), await make_user(db_session)
    base = at(today() - timedelta(days=1))

    def submit(who: User, verdict: str, minutes: int, trial: bool = False) -> Submission:
        return Submission(
            user_id=who.id,
            exercise_id=exercise.id,
            code="print(1)",
            language="python",
            is_trial=trial,
            status="done",
            verdict=verdict,
            score=100 if verdict == "AC" else 0,
            created_at=base + timedelta(minutes=minutes),
        )

    db_session.add_all(
        [
            submit(solver, "WA", 0),
            submit(solver, "WA", 5),
            submit(solver, "AC", 10),
            submit(tryer, "AC", 0, trial=True),
            submit(tryer, "TLE", 3),
        ]
    )
    await db_session.flush()

    body = await insights(api_client, await sign_in(api_client, owner))

    assert body["code"]["submissions"] == 4
    assert body["code"]["learners"] == 2
    assert body["code"]["solve_rate"] == 0.5
    assert body["code"]["median_attempts_to_ac"] == 3.0
    assert body["code"]["verdicts"] == {"AC": 1, "WA": 2, "TLE": 1, "MLE": 0, "RE": 0, "CE": 0}


async def test_qa_answered_means_the_instructor_replied(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Two questions: one the instructor answered after two hours (another
    learner's reply does not count), one nobody from the course answered.
    Half answered, all within a day, a median of 2 hours, one in the backlog."""
    course = await make_course(db_session, owner)
    [lesson] = await add_lessons(db_session, course, 1)
    asker, helper = await make_user(db_session), await make_user(db_session)
    asked = at(today() - timedelta(days=1), 8)
    answered = QaThread(
        lesson_id=lesson.id, user_id=asker.id, title="Hỏi 1", body="?", created_at=asked
    )
    waiting = QaThread(
        lesson_id=lesson.id, user_id=asker.id, title="Hỏi 2", body="?", created_at=asked
    )
    db_session.add_all([answered, waiting])
    await db_session.flush()
    db_session.add_all(
        [
            QaReply(
                thread_id=answered.id,
                user_id=owner.id,
                body="Trả lời",
                is_instructor_reply=True,
                created_at=asked + timedelta(hours=2),
            ),
            QaReply(
                thread_id=waiting.id,
                user_id=helper.id,
                body="Mình cũng không biết",
                is_instructor_reply=False,
                created_at=asked + timedelta(hours=1),
            ),
        ]
    )
    await db_session.flush()
    headers = await sign_in(api_client, owner)

    body = await insights(api_client, headers)

    assert body["qa"]["questions"] == 2
    assert body["qa"]["answered_rate"] == 0.5
    assert body["qa"]["median_first_response_hours"] == 2.0
    assert body["qa"]["answered_within_24h_rate"] == 0.5
    assert body["qa"]["backlog"] == 1
    assert (await overview(api_client, headers))["open_questions"] == 1


async def test_reviews_wishlist_and_carts(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    fan, critic, dreamer = [await make_user(db_session) for _ in range(3)]
    await enrol(db_session, fan, course, when=at(today() - timedelta(days=5)))
    await enrol(db_session, critic, course, when=at(today() - timedelta(days=5)))
    db_session.add_all(
        [
            Review(course_id=course.id, user_id=fan.id, rating=5, comment="Hay"),
            Review(course_id=course.id, user_id=critic.id, rating=3),
            # Wished, then bought: converted. Wished and still dreaming: not.
            Wishlist(
                user_id=fan.id, course_id=course.id, created_at=at(today() - timedelta(days=6))
            ),
            Wishlist(user_id=dreamer.id, course_id=course.id, created_at=at(today())),
        ]
    )
    await db_session.flush()

    body = await insights(api_client, await sign_in(api_client, owner))

    assert body["reviews"]["distribution"] == {"1": 0, "2": 0, "3": 1, "4": 0, "5": 1}
    assert body["reviews"]["commented_rate"] == 0.5
    assert body["reviews"]["new_reviews"] == 2
    assert body["reviews"]["new_review_avg"] == 4.0
    assert body["interest"]["wishlisted_now"] == 2
    assert body["interest"]["wishlist_adds"] == 2
    assert body["interest"]["wishlist_conversion_rate"] == 0.5
    assert body["interest"]["in_carts_now"] == 0


async def test_idle_is_unfinished_with_no_trace_for_thirty_days(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    [lesson] = await add_lessons(db_session, course, 1)
    long_ago = at(today() - timedelta(days=90))
    sleeper = await enrol(db_session, await make_user(db_session), course, when=long_ago)
    await touch(db_session, sleeper, lesson, at(today() - timedelta(days=40)))
    active = await enrol(db_session, await make_user(db_session), course, when=long_ago)
    await touch(db_session, active, lesson, at(today() - timedelta(days=2)))
    await enrol(db_session, await make_user(db_session), course, when=long_ago)  # never started

    body = await insights(api_client, await sign_in(api_client, owner))

    assert body["learning"]["started_rate"] == round(2 / 3, 4)
    assert body["learning"]["idle_rate"] == round(2 / 3, 4)


# --- One course, lesson by lesson ----------------------------------------------


async def test_the_lesson_funnel_shows_where_learners_stop(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    """Four learners, three lessons in order: everybody opened the video, one
    finished the whole course, one stopped halfway through the video."""
    course = await make_course(db_session, owner)
    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    db_session.add(section)
    await db_session.flush()
    asset = VideoAsset(
        storage_key=f"videos/{secrets.token_hex(6)}.mp4", duration_s=600, status="ready"
    )
    db_session.add(asset)
    await db_session.flush()
    video = Lesson(
        section_id=section.id, title="Video", type="video", position=0, video_asset_id=asset.id
    )
    reading = Lesson(section_id=section.id, title="Bài đọc", type="article", position=1)
    last = Lesson(section_id=section.id, title="Cuối", type="article", position=2)
    db_session.add_all([video, reading, last])
    await db_session.flush()
    when = at(today() - timedelta(days=10))

    finisher = await enrol(
        db_session, await make_user(db_session), course, when=when, completed=True
    )
    await touch(db_session, finisher, video, when, completed_at=when, last_position_s=600)
    halfway = await enrol(db_session, await make_user(db_session), course, when=when)
    await touch(db_session, halfway, video, when, last_position_s=300)
    reader = await enrol(db_session, await make_user(db_session), course, when=when)
    await touch(db_session, reader, video, when, completed_at=when, last_position_s=600)
    await touch(db_session, reader, reading, when, completed_at=when)
    await enrol(db_session, await make_user(db_session), course, when=when)

    body = await get(api_client, f"{COURSES}/{course.id}/lessons", await sign_in(api_client, owner))

    assert body["enrollments"] == 4
    assert [lesson["title"] for lesson in body["lessons"]] == ["Video", "Bài đọc", "Cuối"]
    first, second, third = body["lessons"]
    assert (first["started"], first["completed"], first["completion_rate"]) == (3, 2, 0.5)
    assert first["avg_watched"] == round((1 + 0.5 + 1) / 3, 4)
    # The finisher counts as having done every lesson, touched or not.
    assert (second["completed"], third["completed"]) == (2, 1)
    assert second["avg_watched"] is None


async def test_the_lesson_funnel_exports(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    await add_lessons(db_session, course, 2)

    response = await api_client.get(
        f"{COURSES}/{course.id}/lessons/export.xlsx", headers=await sign_in(api_client, owner)
    )

    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    sheet = book["Theo bài học"]
    assert [c.value for c in next(r for r in sheet.iter_rows() if r[0].value == "Chương")][:2] == [
        "Chương",
        "Bài học",
    ]


async def test_a_learner_in_my_cart_is_counted_without_a_price(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, buyer: User
) -> None:
    course = await make_course(db_session, owner)
    cart = Cart(user_id=buyer.id)
    db_session.add(cart)
    await db_session.flush()
    db_session.add(CartItem(cart_id=cart.id, course_id=course.id))
    await db_session.flush()

    body = await insights(api_client, await sign_in(api_client, owner))

    assert body["interest"]["in_carts_now"] == 1
