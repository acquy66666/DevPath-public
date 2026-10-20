"""The instructor's dashboard: who learns, how far they get, what they think.

**No money, anywhere.** Since 20/10/2026 revenue, sales and anything priced
are the admin's (`services/finance.py`); an instructor sees their courses and
their learners. Not even enrolments split by paid/free: purchases times the
public price would put the revenue back on the screen. The instructor's tier
and its share rate are the one money-shaped thing they see
(`services/instructor_tiers.py`), because a reward nobody can see rewards
nobody.

What each figure means -- the definitions the tests pin down:

* **A new student** is somebody whose *first* enrolment in any of this
  instructor's courses began in the window. Two courses on one afternoon are
  two enrolments and one new student.
* **An active learner** in a window left a trace on one of the instructor's
  courses in it: a lesson touched (progress, which a video heartbeat updates),
  a quiz started, code submitted (trial runs too), a question or an answer in
  Q&A, a note. The instructor's own traces never count -- they may try their
  own quiz.
* **Started** is an enrolment with at least one lesson touched; **completion**
  is finished enrolments over enrolments; **progress** is lessons done over
  lessons there are, with a finished enrolment counted as every lesson done.
  `completed_at` is the authority on finishing. All three are null -- not
  zero -- when there is nobody to measure.
* **First-try pass** is, per learner and quiz, whether the first attempt they
  submitted reached the quiz's pass mark. Hard to game: the clock is the
  server's. **Solved** is, per learner and exercise, whether any graded
  (non-trial) submission came back AC -- on hidden tests.
* **Answered** questions have a reply from the instructor
  (`is_instructor_reply`); the response time is to the first such reply.
* **Idle** is an unfinished enrolment with no trace for 30 days.

Nothing is cached or stored; every figure is an aggregate over rows the rest
of the system keeps. The calendar is `services/stats_calendar.py`.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from fastapi import status
from sqlalchemy import (
    Select,
    and_,
    case,
    exists,
    func,
    literal,
    or_,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import (
    CartItem,
    Certificate,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonProgress,
    Note,
    QaReply,
    QaThread,
    Quiz,
    QuizAttempt,
    Review,
    Submission,
    VideoAsset,
    Wishlist,
)
from app.services.stats_calendar import (
    GRANULARITIES,
    PERIODS,
    RATE_PLACES,
    Window,
    bucket_start,
    rate,
    vietnam_today,
    windows,
)

__all__ = ["GRANULARITIES", "PERIODS"]

#: An unfinished enrolment with no trace for this long is idle.
IDLE_AFTER = timedelta(days=30)
#: Verdicts an instructor is shown. SE is the platform failing, not the learner.
LEARNER_VERDICTS = ("AC", "WA", "TLE", "MLE", "RE", "CE")
SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600


def _round(value: float | None, places: int = 2) -> float | None:
    return None if value is None else round(float(value), places)


def _median(column):
    return func.percentile_cont(0.5).within_group(column)


# --- Scope -----------------------------------------------------------------


def _courses(instructor_id: uuid.UUID) -> Select:
    """Every course this instructor has, taken down or not: people still learn
    in a course that was taken down, and its numbers are still theirs."""
    return select(Course.id).where(Course.instructor_id == instructor_id)


def _lessons(courses: Select) -> Select:
    return (
        select(Lesson.id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(CourseSection.course_id.in_(courses))
    )


def _lesson_course(courses: Select):
    """lesson_id -> course_id for the instructor's lessons."""
    return (
        select(Lesson.id.label("lesson_id"), CourseSection.course_id.label("course_id"))
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(CourseSection.course_id.in_(courses))
        .subquery()
    )


def _traces(instructor_id: uuid.UUID, start: datetime, stop: datetime) -> Select:
    """(user_id, at) for every learner trace on the instructor's courses."""
    courses = _courses(instructor_id)
    lessons = _lessons(courses)

    def window(at):
        return and_(at >= start, at < stop)

    return union_all(
        select(Enrollment.user_id.label("user_id"), LessonProgress.updated_at.label("at"))
        .join(Enrollment, Enrollment.id == LessonProgress.enrollment_id)
        .where(Enrollment.course_id.in_(courses), window(LessonProgress.updated_at)),
        select(QuizAttempt.user_id, QuizAttempt.started_at)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(
            Quiz.lesson_id.in_(lessons),
            QuizAttempt.user_id != instructor_id,
            window(QuizAttempt.started_at),
        ),
        select(Submission.user_id, Submission.created_at)
        .join(CodeExercise, CodeExercise.id == Submission.exercise_id)
        .where(
            CodeExercise.lesson_id.in_(lessons),
            Submission.user_id != instructor_id,
            window(Submission.created_at),
        ),
        select(QaThread.user_id, QaThread.created_at).where(
            QaThread.lesson_id.in_(lessons),
            QaThread.user_id != instructor_id,
            window(QaThread.created_at),
        ),
        select(QaReply.user_id, QaReply.created_at)
        .join(QaThread, QaThread.id == QaReply.thread_id)
        .where(
            QaThread.lesson_id.in_(lessons),
            QaReply.user_id != instructor_id,
            window(QaReply.created_at),
        ),
        select(Note.user_id, Note.created_at).where(
            Note.lesson_id.in_(lessons),
            Note.user_id != instructor_id,
            window(Note.created_at),
        ),
    )


# --- Overview --------------------------------------------------------------


@dataclass(slots=True)
class Totals:
    enrollments: int = 0
    new_students: int = 0
    #: Distinct learners active anywhere in the window (not a sum of buckets).
    active_learners: int = 0
    lessons_completed: int = 0
    #: Enrolments that finished the course in the window.
    completions: int = 0
    reviews: int = 0
    #: Average stars of the reviews written in the window.
    review_avg: float | None = None
    questions: int = 0
    wishlist_adds: int = 0


@dataclass(slots=True)
class Point:
    bucket: date
    enrollments: int = 0
    new_students: int = 0
    active_learners: int = 0
    lessons_completed: int = 0
    completions: int = 0
    reviews: int = 0
    questions: int = 0
    wishlist_adds: int = 0


@dataclass(frozen=True, slots=True)
class Overview:
    period: str
    granularity: str
    start: date
    end: date
    current: Totals
    previous: Totals
    series: list[Point]
    # All-time: these describe the instructor, not the window.
    students_total: int
    enrollments_total: int
    courses_published: int
    courses_total: int
    started_rate: float | None
    completion_rate: float | None
    avg_progress: float | None
    median_days_to_complete: float | None
    rating_avg: float | None
    rating_count: int
    certificates_total: int
    open_questions: int


async def _per_bucket(session: AsyncSession, query, points: dict[date, Point], name: str) -> None:
    for bucket, count in await session.execute(query):
        setattr(points[bucket], name, count)


async def _series(session: AsyncSession, instructor_id: uuid.UUID, window: Window) -> list[Point]:
    """One point per bucket of the window, empty ones included."""
    start, stop = window.bounds()
    granularity = window.granularity
    courses = _courses(instructor_id)
    lessons = _lessons(courses)
    points = {bucket: Point(bucket=bucket) for bucket in window.buckets()}

    def counted(column, *where):
        bucket = bucket_start(column, granularity).label("bucket")
        return (
            select(bucket, func.count())
            .where(column >= start, column < stop, *where)
            .group_by(bucket)
        )

    await _per_bucket(
        session,
        counted(Enrollment.created_at, Enrollment.course_id.in_(courses)),
        points,
        "enrollments",
    )
    await _per_bucket(
        session,
        counted(Enrollment.completed_at, Enrollment.course_id.in_(courses)),
        points,
        "completions",
    )
    await _per_bucket(
        session,
        counted(
            LessonProgress.completed_at,
            LessonProgress.enrollment_id.in_(
                select(Enrollment.id).where(Enrollment.course_id.in_(courses))
            ),
        ),
        points,
        "lessons_completed",
    )
    await _per_bucket(
        session, counted(Review.created_at, Review.course_id.in_(courses)), points, "reviews"
    )
    await _per_bucket(
        session,
        counted(
            QaThread.created_at,
            QaThread.lesson_id.in_(lessons),
            QaThread.user_id != instructor_id,
        ),
        points,
        "questions",
    )
    await _per_bucket(
        session,
        counted(Wishlist.created_at, Wishlist.course_id.in_(courses)),
        points,
        "wishlist_adds",
    )

    # Everybody's first enrolment with this instructor, then only those that
    # fall in the window -- filtering first would make last quarter's regular
    # look new the moment they start something else.
    first = (
        select(Enrollment.user_id, func.min(Enrollment.created_at).label("first_at"))
        .where(Enrollment.course_id.in_(courses))
        .group_by(Enrollment.user_id)
        .subquery()
    )
    arrived = bucket_start(first.c.first_at, granularity).label("bucket")
    await _per_bucket(
        session,
        select(arrived, func.count())
        .where(first.c.first_at >= start, first.c.first_at < stop)
        .group_by(arrived),
        points,
        "new_students",
    )

    traces = _traces(instructor_id, start, stop).subquery()
    active = bucket_start(traces.c.at, granularity).label("bucket")
    await _per_bucket(
        session,
        select(active, func.count(func.distinct(traces.c.user_id))).group_by(active),
        points,
        "active_learners",
    )
    return list(points.values())


async def _totals(
    session: AsyncSession, instructor_id: uuid.UUID, window: Window, series: list[Point]
) -> Totals:
    start, stop = window.bounds()
    traces = _traces(instructor_id, start, stop).subquery()
    active = await session.scalar(select(func.count(func.distinct(traces.c.user_id))))
    review_avg = await session.scalar(
        select(func.avg(Review.rating)).where(
            Review.course_id.in_(_courses(instructor_id)),
            Review.created_at >= start,
            Review.created_at < stop,
        )
    )
    return Totals(
        enrollments=sum(p.enrollments for p in series),
        new_students=sum(p.new_students for p in series),
        active_learners=active or 0,
        lessons_completed=sum(p.lessons_completed for p in series),
        completions=sum(p.completions for p in series),
        reviews=sum(p.reviews for p in series),
        review_avg=_round(review_avg),
        questions=sum(p.questions for p in series),
        wishlist_adds=sum(p.wishlist_adds for p in series),
    )


def _lesson_counts(courses: Select):
    return (
        select(CourseSection.course_id, func.count(Lesson.id).label("lessons"))
        .join(Lesson, Lesson.section_id == CourseSection.id)
        .where(CourseSection.course_id.in_(courses))
        .group_by(CourseSection.course_id)
        .subquery()
    )


def _per_enrolment(courses: Select):
    """One row per enrolment: lessons done, whether anything was touched, and
    when it was first and last touched."""
    return (
        select(
            Enrollment.id.label("enrollment_id"),
            Enrollment.course_id,
            Enrollment.created_at,
            Enrollment.completed_at,
            func.count(LessonProgress.id)
            .filter(LessonProgress.completed_at.is_not(None))
            .label("done"),
            func.count(LessonProgress.id).label("touched"),
            func.min(LessonProgress.created_at).label("first_touch"),
            func.max(LessonProgress.updated_at).label("last_touch"),
        )
        .outerjoin(LessonProgress, LessonProgress.enrollment_id == Enrollment.id)
        .where(Enrollment.course_id.in_(courses))
        .group_by(Enrollment.id)
        .subquery()
    )


def _done_capped(per_enrolment, lessons):
    """Lessons done, a finished enrolment counting as all of them, and nobody
    counting as more than all of them."""
    return case(
        (per_enrolment.c.completed_at.is_not(None), func.coalesce(lessons.c.lessons, 0)),
        else_=func.least(per_enrolment.c.done, func.coalesce(lessons.c.lessons, 0)),
    )


def _open_questions(instructor_id: uuid.UUID, lessons: Select):
    """Learner questions with no instructor answer that nobody marked resolved."""
    answered = exists().where(
        QaReply.thread_id == QaThread.id, QaReply.is_instructor_reply.is_(True)
    )
    return and_(
        QaThread.lesson_id.in_(lessons),
        QaThread.user_id != instructor_id,
        QaThread.resolved_at.is_(None),
        ~answered,
    )


async def overview(
    session: AsyncSession,
    instructor_id: uuid.UUID,
    period: str,
    *,
    now: datetime | None = None,
) -> Overview:
    """Totals for the period and the one before it, the series behind the
    chart, and the all-time figures that describe the instructor."""
    today = vietnam_today(now)
    current, previous = windows(period, today)
    series = await _series(session, instructor_id, current)
    previous_series = await _series(session, instructor_id, previous)
    courses = _courses(instructor_id)
    lessons = _lessons(courses)

    per_enrolment = _per_enrolment(courses)
    lesson_counts = _lesson_counts(courses)
    enrolments, completed, started, done, possible, median_days = (
        await session.execute(
            select(
                func.count(),
                func.count(per_enrolment.c.completed_at),
                func.count().filter(per_enrolment.c.touched > 0),
                func.coalesce(func.sum(_done_capped(per_enrolment, lesson_counts)), 0),
                func.coalesce(func.sum(func.coalesce(lesson_counts.c.lessons, 0)), 0),
                _median(
                    func.extract("epoch", per_enrolment.c.completed_at - per_enrolment.c.created_at)
                    / SECONDS_PER_DAY
                ),
            )
            .select_from(per_enrolment)
            .outerjoin(lesson_counts, lesson_counts.c.course_id == per_enrolment.c.course_id)
        )
    ).one()

    students = await session.scalar(
        select(func.count(func.distinct(Enrollment.user_id))).where(
            Enrollment.course_id.in_(courses)
        )
    )
    published, total = (
        await session.execute(
            select(
                func.count().filter(Course.status == "published"),
                func.count(),
            ).where(Course.instructor_id == instructor_id, Course.deleted_at.is_(None))
        )
    ).one()
    rating_avg, rating_count = (
        await session.execute(
            select(func.avg(Review.rating), func.count()).where(Review.course_id.in_(courses))
        )
    ).one()
    certificates = await session.scalar(
        select(func.count())
        .select_from(Certificate)
        .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
        .where(Enrollment.course_id.in_(courses))
    )
    open_questions = await session.scalar(
        select(func.count()).select_from(QaThread).where(_open_questions(instructor_id, lessons))
    )

    return Overview(
        period=period,
        granularity=current.granularity,
        start=current.start,
        # A month-long bar runs to the end of the month; the range printed
        # above the chart stops at today.
        end=min(current.stop - timedelta(days=1), today),
        current=await _totals(session, instructor_id, current, series),
        previous=await _totals(session, instructor_id, previous, previous_series),
        series=series,
        students_total=students or 0,
        enrollments_total=enrolments,
        courses_published=published,
        courses_total=total,
        started_rate=rate(started, enrolments),
        completion_rate=rate(completed, enrolments),
        avg_progress=rate(int(done), int(possible)),
        median_days_to_complete=_round(median_days, 1),
        rating_avg=_round(rating_avg),
        rating_count=rating_count,
        certificates_total=certificates or 0,
        open_questions=open_questions or 0,
    )


# --- Insights --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LearningInsights:
    started_rate: float | None
    idle_rate: float | None
    median_days_to_first_lesson: float | None
    median_days_to_complete: float | None


@dataclass(frozen=True, slots=True)
class QuizInsights:
    attempts: int
    learners: int
    median_score: float | None
    first_try_pass_rate: float | None
    expired_rate: float | None


@dataclass(frozen=True, slots=True)
class CodeInsights:
    submissions: int
    learners: int
    solve_rate: float | None
    median_attempts_to_ac: float | None
    verdicts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ReviewInsights:
    #: All-time count per star, 1..5, zeros included.
    distribution: dict[int, int]
    commented_rate: float | None
    new_reviews: int
    new_review_avg: float | None


@dataclass(frozen=True, slots=True)
class QaInsights:
    questions: int
    answered_rate: float | None
    median_first_response_hours: float | None
    answered_within_24h_rate: float | None
    resolved_rate: float | None
    #: All-time: open questions still waiting for the instructor.
    backlog: int


@dataclass(frozen=True, slots=True)
class InterestInsights:
    wishlist_adds: int
    wishlisted_now: int
    #: Wishlist rows whose person later enrolled in that course, all-time.
    wishlist_conversion_rate: float | None
    in_carts_now: int


@dataclass(frozen=True, slots=True)
class Insights:
    period: str
    start: date
    end: date
    learning: LearningInsights
    quiz: QuizInsights
    code: CodeInsights
    reviews: ReviewInsights
    qa: QaInsights
    interest: InterestInsights


def _first_quiz_attempts(instructor_id: uuid.UUID, lessons: Select):
    """Each learner's first submitted attempt at each quiz, with its pass mark."""
    ranked = (
        select(
            QuizAttempt.user_id,
            QuizAttempt.quiz_id,
            Quiz.lesson_id,
            QuizAttempt.score,
            QuizAttempt.submitted_at,
            Quiz.pass_score,
            func.row_number()
            .over(
                partition_by=(QuizAttempt.user_id, QuizAttempt.quiz_id),
                order_by=(QuizAttempt.submitted_at, QuizAttempt.id),
            )
            .label("n"),
        )
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(
            Quiz.lesson_id.in_(lessons),
            QuizAttempt.user_id != instructor_id,
            QuizAttempt.submitted_at.is_not(None),
        )
        .subquery()
    )
    return select(ranked).where(ranked.c.n == 1).subquery()


def _code_pairs(instructor_id: uuid.UUID, lessons: Select, start=None, stop=None):
    """(learner, exercise) pairs with graded submissions, and whether solved."""
    where = [
        CodeExercise.lesson_id.in_(lessons),
        Submission.user_id != instructor_id,
        Submission.is_trial.is_(False),
    ]
    if start is not None:
        where += [Submission.created_at >= start, Submission.created_at < stop]
    return (
        select(
            Submission.user_id,
            Submission.exercise_id,
            CodeExercise.lesson_id,
            func.bool_or(Submission.verdict == "AC").label("solved"),
            func.min(Submission.created_at).filter(Submission.verdict == "AC").label("first_ac"),
        )
        .join(CodeExercise, CodeExercise.id == Submission.exercise_id)
        .where(*where)
        .group_by(Submission.user_id, Submission.exercise_id, CodeExercise.lesson_id)
        .subquery()
    )


async def insights(
    session: AsyncSession,
    instructor_id: uuid.UUID,
    period: str,
    *,
    now: datetime | None = None,
) -> Insights:
    moment = now or datetime.now(UTC)
    today = vietnam_today(moment)
    window, _ = windows(period, today)
    start, stop = window.bounds()
    courses = _courses(instructor_id)
    lessons = _lessons(courses)

    # Learning, all-time.
    per_enrolment = _per_enrolment(courses)
    last_trace = func.coalesce(per_enrolment.c.last_touch, per_enrolment.c.created_at)
    enrolments, started, unfinished, idle, to_first, to_complete = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(per_enrolment.c.touched > 0),
                func.count().filter(per_enrolment.c.completed_at.is_(None)),
                func.count().filter(
                    per_enrolment.c.completed_at.is_(None), last_trace < moment - IDLE_AFTER
                ),
                _median(
                    func.extract("epoch", per_enrolment.c.first_touch - per_enrolment.c.created_at)
                    / SECONDS_PER_DAY
                ),
                _median(
                    func.extract("epoch", per_enrolment.c.completed_at - per_enrolment.c.created_at)
                    / SECONDS_PER_DAY
                ),
            ).select_from(per_enrolment)
        )
    ).one()
    learning = LearningInsights(
        started_rate=rate(started, enrolments),
        idle_rate=rate(idle, unfinished),
        median_days_to_first_lesson=_round(
            None if to_first is None else max(float(to_first), 0.0), 1
        ),
        median_days_to_complete=_round(to_complete, 1),
    )

    # Quizzes in the window.
    attempts, quiz_learners, median_score, expired = (
        await session.execute(
            select(
                func.count(),
                func.count(func.distinct(QuizAttempt.user_id)),
                _median(QuizAttempt.score),
                func.count().filter(QuizAttempt.expired.is_(True)),
            )
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                Quiz.lesson_id.in_(lessons),
                QuizAttempt.user_id != instructor_id,
                QuizAttempt.submitted_at >= start,
                QuizAttempt.submitted_at < stop,
            )
        )
    ).one()
    first = _first_quiz_attempts(instructor_id, lessons)
    firsts, passed_first = (
        await session.execute(
            select(func.count(), func.count().filter(first.c.score >= first.c.pass_score)).where(
                first.c.submitted_at >= start, first.c.submitted_at < stop
            )
        )
    ).one()
    quiz = QuizInsights(
        attempts=attempts,
        learners=quiz_learners,
        median_score=_round(median_score, 1),
        first_try_pass_rate=rate(passed_first, firsts),
        expired_rate=rate(expired, attempts),
    )

    # Code in the window.
    graded = and_(
        CodeExercise.lesson_id.in_(lessons),
        Submission.user_id != instructor_id,
        Submission.is_trial.is_(False),
        Submission.created_at >= start,
        Submission.created_at < stop,
    )
    submissions, code_learners = (
        await session.execute(
            select(func.count(), func.count(func.distinct(Submission.user_id)))
            .join(CodeExercise, CodeExercise.id == Submission.exercise_id)
            .where(graded)
        )
    ).one()
    verdicts = {verdict: 0 for verdict in LEARNER_VERDICTS}
    for verdict, count in await session.execute(
        select(Submission.verdict, func.count())
        .join(CodeExercise, CodeExercise.id == Submission.exercise_id)
        .where(graded, Submission.verdict.in_(LEARNER_VERDICTS))
        .group_by(Submission.verdict)
    ):
        verdicts[verdict] = count
    pairs = _code_pairs(instructor_id, lessons, start, stop)
    pair_count, solved = (
        await session.execute(select(func.count(), func.count().filter(pairs.c.solved)))
    ).one()
    # Graded submissions up to and including the first AC, for pairs whose
    # first AC ever falls in the window.
    every_pair = _code_pairs(instructor_id, lessons)
    tries = (
        select(func.count().label("tries"))
        .select_from(Submission)
        .join(
            every_pair,
            and_(
                every_pair.c.user_id == Submission.user_id,
                every_pair.c.exercise_id == Submission.exercise_id,
            ),
        )
        .where(
            Submission.is_trial.is_(False),
            Submission.created_at <= every_pair.c.first_ac,
            every_pair.c.first_ac >= start,
            every_pair.c.first_ac < stop,
        )
        .group_by(every_pair.c.user_id, every_pair.c.exercise_id)
        .subquery()
    )
    median_tries = await session.scalar(select(_median(tries.c.tries)))
    code = CodeInsights(
        submissions=submissions,
        learners=code_learners,
        solve_rate=rate(solved, pair_count),
        median_attempts_to_ac=_round(median_tries, 1),
        verdicts=verdicts,
    )

    # Reviews.
    distribution = {stars: 0 for stars in range(1, 6)}
    for stars, count in await session.execute(
        select(Review.rating, func.count())
        .where(Review.course_id.in_(courses))
        .group_by(Review.rating)
    ):
        distribution[stars] = count
    review_total, commented = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(func.length(func.btrim(func.coalesce(Review.comment, ""))) > 0),
            ).where(Review.course_id.in_(courses))
        )
    ).one()
    new_reviews, new_avg = (
        await session.execute(
            select(func.count(), func.avg(Review.rating)).where(
                Review.course_id.in_(courses),
                Review.created_at >= start,
                Review.created_at < stop,
            )
        )
    ).one()
    reviews = ReviewInsights(
        distribution=distribution,
        commented_rate=rate(commented, review_total),
        new_reviews=new_reviews,
        new_review_avg=_round(new_avg),
    )

    # Q&A in the window.
    first_reply = (
        select(QaReply.thread_id, func.min(QaReply.created_at).label("at"))
        .where(QaReply.is_instructor_reply.is_(True))
        .group_by(QaReply.thread_id)
        .subquery()
    )
    waited = func.extract("epoch", first_reply.c.at - QaThread.created_at)
    questions, answered, median_wait, within_day, resolved = (
        await session.execute(
            select(
                func.count(),
                func.count(first_reply.c.at),
                _median(waited / SECONDS_PER_HOUR),
                func.count().filter(waited <= 24 * SECONDS_PER_HOUR),
                func.count(QaThread.resolved_at),
            )
            .select_from(QaThread)
            .outerjoin(first_reply, first_reply.c.thread_id == QaThread.id)
            .where(
                QaThread.lesson_id.in_(lessons),
                QaThread.user_id != instructor_id,
                QaThread.created_at >= start,
                QaThread.created_at < stop,
            )
        )
    ).one()
    backlog = await session.scalar(
        select(func.count()).select_from(QaThread).where(_open_questions(instructor_id, lessons))
    )
    qa = QaInsights(
        questions=questions,
        answered_rate=rate(answered, questions),
        median_first_response_hours=_round(median_wait, 1),
        answered_within_24h_rate=rate(within_day, questions),
        resolved_rate=rate(resolved, questions),
        backlog=backlog or 0,
    )

    # Interest.
    enrolled_after = exists().where(
        Enrollment.user_id == Wishlist.user_id,
        Enrollment.course_id == Wishlist.course_id,
        Enrollment.created_at >= Wishlist.created_at,
    )
    wishlisted, converted, adds = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(enrolled_after),
                func.count().filter(Wishlist.created_at >= start, Wishlist.created_at < stop),
            ).where(Wishlist.course_id.in_(courses))
        )
    ).one()
    in_carts = await session.scalar(
        select(func.count()).select_from(CartItem).where(CartItem.course_id.in_(courses))
    )
    interest = InterestInsights(
        wishlist_adds=adds,
        wishlisted_now=wishlisted,
        wishlist_conversion_rate=rate(converted, wishlisted),
        in_carts_now=in_carts or 0,
    )

    return Insights(
        period=period,
        start=window.start,
        end=min(window.stop - timedelta(days=1), today),
        learning=learning,
        quiz=quiz,
        code=code,
        reviews=reviews,
        qa=qa,
        interest=interest,
    )


# --- Per course ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CourseStats:
    course: Course
    students: int
    new_enrollments: int
    completed: int
    lessons_count: int
    started_rate: float | None
    completion_rate: float | None
    avg_progress: float | None
    rating_avg: float | None
    rating_count: int
    open_questions: int
    wishlisted: int
    quiz_first_try_pass_rate: float | None
    code_solve_rate: float | None


async def course_stats(
    session: AsyncSession,
    instructor_id: uuid.UUID,
    period: str,
    *,
    page: int,
    page_size: int,
    now: datetime | None = None,
) -> tuple[list[CourseStats], int]:
    """One row per course, most students first.

    A course that was taken down stays listed while anybody is still enrolled
    in it -- soft delete exists so that those people keep their course, and
    its instructor keeps seeing how they get on. One that nobody joined is gone.
    """
    window, _ = windows(period, vietnam_today(now))
    start, stop = window.bounds()
    courses = _courses(instructor_id)
    lessons = _lessons(courses)
    lesson_course = _lesson_course(courses)

    per_enrolment = _per_enrolment(courses)
    lesson_counts = _lesson_counts(courses)
    enrolled = (
        select(
            per_enrolment.c.course_id,
            func.count().label("students"),
            func.count(per_enrolment.c.completed_at).label("completed"),
            func.count()
            .filter(per_enrolment.c.created_at >= start, per_enrolment.c.created_at < stop)
            .label("new_enrollments"),
            func.count().filter(per_enrolment.c.touched > 0).label("started"),
            func.sum(_done_capped(per_enrolment, lesson_counts)).label("done"),
        )
        .select_from(per_enrolment)
        .outerjoin(lesson_counts, lesson_counts.c.course_id == per_enrolment.c.course_id)
        .group_by(per_enrolment.c.course_id)
        .subquery()
    )
    open_questions = (
        select(lesson_course.c.course_id, func.count().label("open"))
        .select_from(QaThread)
        .join(lesson_course, lesson_course.c.lesson_id == QaThread.lesson_id)
        .where(_open_questions(instructor_id, lessons))
        .group_by(lesson_course.c.course_id)
        .subquery()
    )
    wished = (
        select(Wishlist.course_id, func.count().label("wished"))
        .where(Wishlist.course_id.in_(courses))
        .group_by(Wishlist.course_id)
        .subquery()
    )
    first = _first_quiz_attempts(instructor_id, lessons)
    quiz = (
        select(
            lesson_course.c.course_id,
            func.count().label("firsts"),
            func.count().filter(first.c.score >= first.c.pass_score).label("passed"),
        )
        .select_from(first)
        .join(lesson_course, lesson_course.c.lesson_id == first.c.lesson_id)
        .group_by(lesson_course.c.course_id)
        .subquery()
    )
    pairs = _code_pairs(instructor_id, lessons)
    code = (
        select(
            lesson_course.c.course_id,
            func.count().label("pairs"),
            func.count().filter(pairs.c.solved).label("solved"),
        )
        .select_from(pairs)
        .join(lesson_course, lesson_course.c.lesson_id == pairs.c.lesson_id)
        .group_by(lesson_course.c.course_id)
        .subquery()
    )

    students = func.coalesce(enrolled.c.students, 0)
    rows = (
        select(
            Course,
            students.label("students"),
            func.coalesce(enrolled.c.new_enrollments, 0).label("new_enrollments"),
            func.coalesce(enrolled.c.completed, 0).label("completed"),
            func.coalesce(enrolled.c.started, 0).label("started"),
            func.coalesce(enrolled.c.done, 0).label("done"),
            func.coalesce(lesson_counts.c.lessons, 0).label("lessons"),
            func.coalesce(open_questions.c.open, 0).label("open"),
            func.coalesce(wished.c.wished, 0).label("wished"),
            func.coalesce(quiz.c.firsts, 0).label("quiz_firsts"),
            func.coalesce(quiz.c.passed, 0).label("quiz_passed"),
            func.coalesce(code.c.pairs, 0).label("code_pairs"),
            func.coalesce(code.c.solved, 0).label("code_solved"),
        )
        .outerjoin(enrolled, enrolled.c.course_id == Course.id)
        .outerjoin(lesson_counts, lesson_counts.c.course_id == Course.id)
        .outerjoin(open_questions, open_questions.c.course_id == Course.id)
        .outerjoin(wished, wished.c.course_id == Course.id)
        .outerjoin(quiz, quiz.c.course_id == Course.id)
        .outerjoin(code, code.c.course_id == Course.id)
        .where(
            Course.instructor_id == instructor_id,
            or_(Course.deleted_at.is_(None), students > 0),
        )
    )

    total = await session.scalar(select(func.count()).select_from(rows.subquery()))
    result = await session.execute(
        rows.order_by(students.desc(), Course.created_at.desc(), Course.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        CourseStats(
            course=row.Course,
            students=row.students,
            new_enrollments=row.new_enrollments,
            completed=row.completed,
            lessons_count=row.lessons,
            started_rate=rate(row.started, row.students),
            completion_rate=rate(row.completed, row.students),
            avg_progress=rate(int(row.done), row.students * row.lessons),
            rating_avg=_round(row.Course.rating_avg) if row.Course.rating_count else None,
            rating_count=row.Course.rating_count,
            open_questions=row.open,
            wishlisted=row.wished,
            quiz_first_try_pass_rate=rate(row.quiz_passed, row.quiz_firsts),
            code_solve_rate=rate(row.code_solved, row.code_pairs),
        )
        for row in result
    ]
    return items, total or 0


# --- One course, lesson by lesson ------------------------------------------


@dataclass(frozen=True, slots=True)
class LessonStats:
    lesson_id: uuid.UUID
    section_title: str
    title: str
    type: str
    started: int
    completed: int
    #: Of the course's enrolments, the share that finished this lesson.
    completion_rate: float | None
    #: Video only: how far into it learners got on average (finished = all).
    avg_watched: float | None
    quiz_first_try_pass_rate: float | None
    code_solve_rate: float | None
    questions: int
    notes: int


@dataclass(frozen=True, slots=True)
class CourseFunnel:
    course: Course
    enrollments: int
    lessons: list[LessonStats] = field(default_factory=list)


class CourseNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "COURSE_NOT_FOUND"


async def course_funnel(
    session: AsyncSession, instructor_id: uuid.UUID, course_id: uuid.UUID
) -> CourseFunnel:
    """Where learners stop: every lesson in order, with how many finished it.

    A finished enrolment counts as having finished every lesson, as it does
    for progress, so the funnel never falls below the completion rate.
    """
    course = await session.scalar(
        select(Course).where(Course.id == course_id, Course.instructor_id == instructor_id)
    )
    if course is None:
        raise CourseNotFoundError("Không tìm thấy khóa học này trong các khóa bạn dạy")

    enrolments, finished = (
        await session.execute(
            select(func.count(), func.count(Enrollment.completed_at)).where(
                Enrollment.course_id == course_id
            )
        )
    ).one()

    progress = (
        select(
            LessonProgress.lesson_id,
            func.count().label("started"),
            func.count()
            .filter(LessonProgress.completed_at.is_not(None), Enrollment.completed_at.is_(None))
            .label("completed_unfinished"),
            func.avg(
                case(
                    (
                        or_(
                            LessonProgress.completed_at.is_not(None),
                            Enrollment.completed_at.is_not(None),
                        ),
                        literal(1.0),
                    ),
                    else_=func.least(
                        LessonProgress.last_position_s
                        / func.nullif(func.coalesce(VideoAsset.duration_s, 0), 0),
                        1.0,
                    ),
                )
            ).label("watched"),
        )
        .join(Enrollment, Enrollment.id == LessonProgress.enrollment_id)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .outerjoin(VideoAsset, VideoAsset.id == Lesson.video_asset_id)
        .where(Enrollment.course_id == course_id)
        .group_by(LessonProgress.lesson_id)
        .subquery()
    )
    lessons = select(Lesson.id).join(CourseSection).where(CourseSection.course_id == course_id)
    first = _first_quiz_attempts(instructor_id, lessons)
    quiz = (
        select(
            first.c.lesson_id,
            func.count().label("firsts"),
            func.count().filter(first.c.score >= first.c.pass_score).label("passed"),
        )
        .group_by(first.c.lesson_id)
        .subquery()
    )
    pairs = _code_pairs(instructor_id, lessons)
    code = (
        select(
            pairs.c.lesson_id,
            func.count().label("pairs"),
            func.count().filter(pairs.c.solved).label("solved"),
        )
        .group_by(pairs.c.lesson_id)
        .subquery()
    )
    questions = (
        select(QaThread.lesson_id, func.count().label("questions"))
        .where(QaThread.lesson_id.in_(lessons), QaThread.user_id != instructor_id)
        .group_by(QaThread.lesson_id)
        .subquery()
    )
    notes = (
        select(Note.lesson_id, func.count().label("notes"))
        .where(Note.lesson_id.in_(lessons), Note.user_id != instructor_id)
        .group_by(Note.lesson_id)
        .subquery()
    )

    rows = await session.execute(
        select(
            Lesson.id,
            Lesson.title,
            Lesson.type,
            CourseSection.title.label("section_title"),
            func.coalesce(progress.c.started, 0),
            func.coalesce(progress.c.completed_unfinished, 0),
            progress.c.watched,
            func.coalesce(quiz.c.firsts, 0),
            func.coalesce(quiz.c.passed, 0),
            func.coalesce(code.c.pairs, 0),
            func.coalesce(code.c.solved, 0),
            func.coalesce(questions.c.questions, 0),
            func.coalesce(notes.c.notes, 0),
        )
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .outerjoin(progress, progress.c.lesson_id == Lesson.id)
        .outerjoin(quiz, quiz.c.lesson_id == Lesson.id)
        .outerjoin(code, code.c.lesson_id == Lesson.id)
        .outerjoin(questions, questions.c.lesson_id == Lesson.id)
        .outerjoin(notes, notes.c.lesson_id == Lesson.id)
        .where(CourseSection.course_id == course_id)
        .order_by(CourseSection.position, Lesson.position)
    )

    items = []
    for (
        lesson_id,
        title,
        lesson_type,
        section_title,
        started,
        completed_unfinished,
        watched,
        quiz_firsts,
        quiz_passed,
        code_pairs,
        code_solved,
        question_count,
        note_count,
    ) in rows:
        completed = finished + completed_unfinished
        items.append(
            LessonStats(
                lesson_id=lesson_id,
                section_title=section_title,
                title=title,
                type=lesson_type,
                started=started,
                completed=completed,
                completion_rate=rate(completed, enrolments),
                avg_watched=(
                    round(float(watched), RATE_PLACES)
                    if lesson_type == "video" and watched is not None
                    else None
                ),
                quiz_first_try_pass_rate=rate(quiz_passed, quiz_firsts),
                code_solve_rate=rate(code_solved, code_pairs),
                questions=question_count,
                notes=note_count,
            )
        )
    return CourseFunnel(course=course, enrollments=enrolments, lessons=items)
