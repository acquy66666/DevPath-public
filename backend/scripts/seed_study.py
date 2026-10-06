"""Ten weeks of studying, so the leaderboard has a race to show.

    python -m scripts.seed_study
    python -m scripts.seed_study --purge

XP only exists from the day the feature shipped, and nobody on a development
machine studies on more than one day -- so the week, the month and all time
would be the same board with the same three names. This has the forty demo
buyers of `scripts.seed_sales` study what they bought, and some of them join a
free course or two as well, over the past ten weeks: some every day, some in
bursts, some giving up half-way.

**Every lesson is finished through the real services.** A lesson is ticked by
`progress.save_position(completed=True)`, a quiz is sat through
`quiz.start_attempt` / `quiz.submit_attempt` (and sometimes failed, then
retried), a free course is joined through `enrollments.enrol_free`. So the XP,
the course completions and the streak days are the ones the platform would
have recorded. Code exercises are skipped: they need the grading sandbox, and
a student can move on without solving one.

**The one thing written directly is the clock.** The services stamp rows with
`now()`; afterwards each completion, attempt, award and enrolment is moved back
to the moment in the plan, and an account is moved before a free course joined
ahead of its first purchase. The streak is then replayed day by day through
`gamification.record_active_day`, because the services counted every action as
today. Last, the leaderboard is rebuilt from the ledger.

**Its own learners**: the buyers (`nguoimuaNN@sales.devpath.example`), never
the seeded learners -- `scripts.seed_interactions` and its tests pin exactly
what those study. Run **after `scripts.seed_sales`**. The free enrolments feed
the recommender like any other, so **`--purge` before `scripts.eval_recommender`**.

Dates are relative to when it runs, and the plan is seeded -- one generator
per buyer and course, drawn by calendar day -- so every machine gets the same
studying counted back from its own today, at whatever hour it runs: only
today's sittings are squeezed into the part of today that has passed (and in
the first five minutes after midnight, left out). Idempotent: if the
buyers have studied anything, it writes nothing. `--purge` removes every
completion, attempt, award, streak and free enrolment of the buyers, recounts
the students of the free courses and rebuilds the leaderboard -- the account
dates stay where they are, still before every purchase.
"""

import argparse
import asyncio
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import VIETNAM, start_of_day, today_in_vietnam
from app.core.db import SessionLocal
from app.models import (
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    LessonProgress,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Streak,
    User,
    XpEvent,
)
from app.services import certificates, course_stats, gamification, leaderboard
from app.services import enrollments as enrollments_service
from app.services import progress as progress_service
from app.services import quiz as quiz_service
from scripts.seed_sales import backdate_sign_ups, buyer_emails, fit_to_now

STUDY_DAYS = 70
#: Fixed, so every machine gets the same studying.
RANDOM_SEED = 20260928

#: The free courses with a curriculum worth walking through.
FREE_COURSES = (
    "python-co-ban-cho-nguoi-moi-bat-dau",
    "javascript-hien-dai-es6-va-dom",
    "xay-dung-rest-api-voi-fastapi",
)
QUIZ_PASS_CHANCE = 0.75
MAX_QUIZ_TRIES = 3


@dataclass(frozen=True, slots=True)
class Step:
    """One lesson of a course, as the plan sees it."""

    lesson_id: uuid.UUID
    #: The quiz on it, if the lesson is a quiz lesson.
    quiz_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class Join:
    buyer: str
    course: str
    day: date


@dataclass(frozen=True, slots=True)
class Action:
    buyer: str
    course: str
    step: Step
    at: datetime
    #: For a quiz: whether this sitting passes. Ignored for other lessons.
    passes: bool = True


def diligence(rng: random.Random, buyers: list[str]) -> dict[str, float]:
    """How keen each buyer is, 0 to 1. Drives everything else."""
    return {buyer: rng.random() for buyer in buyers}


def plan_joins(rng: random.Random, keenness: dict[str, float], today: date) -> list[Join]:
    """Which free courses each buyer also joins, and when."""
    joins = []
    for buyer, keen in keenness.items():
        count = 2 if keen > 0.66 else 1 if keen > 0.25 else 0
        for course in rng.sample(FREE_COURSES, count):
            joins.append(Join(buyer, course, today - timedelta(days=rng.randint(7, STUDY_DAYS))))
    return joins


def study_rng(buyer: str, course: str) -> random.Random:
    """The generator one buyer's plan for one course is drawn from.

    One per pair, never shared: with a single generator every plan depends on
    every plan drawn before it, so two enrolments made in the same second --
    which Postgres returns in either order -- reshuffled the whole run.
    """
    return random.Random(f"{RANDOM_SEED}:{buyer}:{course}")


def plan_study(
    rng: random.Random,
    keen: float,
    buyer: str,
    course: str,
    steps: list[Step],
    start: date,
    now: datetime,
) -> list[Action]:
    """One buyer working through one course from `start`, never past `now`.

    A study day finishes one to three lessons. Keen buyers come back the next
    day more often than not; the rest leave gaps of up to a week, and every
    buyer may drop the course between two study days. A quiz is failed now
    and then and retried on the next study day.

    The plan is drawn by calendar day up to today, and the hour the script
    runs draws nothing: today's sittings are fitted into the part of today
    that has happened (`fit_to_now`), so the same lessons are studied on the
    same days whenever it runs.
    """
    today = now.astimezone(VIETNAM).date()
    actions: list[Action] = []
    position = 0
    tries = 0
    day = start + timedelta(days=rng.randint(0, 3))

    while position < len(steps) and day <= today:
        # One sitting: a start time, then each lesson a little after the last,
        # so the day's lessons happen in the order they were studied.
        at = start_of_day(day) + timedelta(hours=rng.randint(7, 22), minutes=rng.randint(0, 59))
        for sitting in range(rng.randint(1, 3)):
            if position >= len(steps):
                break
            if sitting > 0:
                at += timedelta(minutes=rng.randint(8, 30))
            step = steps[position]
            passes = (
                step.quiz_id is None
                or tries + 1 >= MAX_QUIZ_TRIES
                or (rng.random() < QUIZ_PASS_CHANCE)
            )
            actions.append(Action(buyer, course, step, at, passes))
            if passes:
                position += 1
                tries = 0
            else:
                tries += 1
                break  # a failed quiz ends the day
        if rng.random() > 0.55 + 0.45 * keen:
            break  # dropped the course
        day += timedelta(days=1 if rng.random() < 0.3 + 0.65 * keen else rng.randint(2, 6))

    fitted = []
    for action in actions:
        at = fit_to_now(action.at, now)
        if at is None:
            break  # just after midnight: the rest is today, and none of it has happened
        fitted.append(replace(action, at=at))
    return fitted


# --- Reading what there is to study ------------------------------------------


async def _buyers(session: AsyncSession) -> dict[str, User]:
    rows = await session.scalars(select(User).where(User.email.in_(buyer_emails())))
    return {user.email: user for user in rows}


async def _steps(session: AsyncSession, course_id: uuid.UUID) -> list[Step]:
    """Lessons in reading order. Code exercises are left out: see the docstring."""
    rows = await session.execute(
        select(Lesson.id, Lesson.type, Quiz.id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .outerjoin(Quiz, (Quiz.lesson_id == Lesson.id) & Quiz.is_published)
        .where(CourseSection.course_id == course_id, Lesson.type != "code_exercise")
        .order_by(CourseSection.position, Lesson.position)
    )
    return [
        Step(lesson_id, quiz_id if kind == "quiz" else None)
        for lesson_id, kind, quiz_id in rows
        # A quiz lesson whose quiz is not published cannot be finished.
        if kind != "quiz" or quiz_id is not None
    ]


async def _answers(session: AsyncSession, quiz_id: uuid.UUID) -> tuple[list[int], list[int]]:
    """The right answers, and a set of wrong ones, in question order."""
    rows = await session.execute(
        select(QuizQuestion.correct_index, func.jsonb_array_length(QuizQuestion.options))
        .where(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.position)
    )
    right, wrong = [], []
    for correct, options in rows:
        right.append(correct)
        wrong.append((correct + 1) % options)
    return right, wrong


async def already_studied(session: AsyncSession) -> bool:
    buyer_ids = select(User.id).where(User.email.in_(buyer_emails()))
    return bool(
        await session.scalar(select(func.count()).where(XpEvent.user_id.in_(buyer_ids)))
    ) or bool(
        await session.scalar(
            select(func.count()).where(
                Enrollment.user_id.in_(buyer_ids), Enrollment.source == "free"
            )
        )
    )


# --- Doing it -----------------------------------------------------------------


@dataclass
class Written:
    joined: int = 0
    lessons: int = 0
    quizzes_passed: int = 0
    quizzes_failed: int = 0


async def seed_study(session: AsyncSession, *, now: datetime | None = None) -> Written:
    written = Written()
    buyers = await _buyers(session)
    if not buyers or await already_studied(session):
        return written

    now = now or datetime.now(UTC)
    today = today_in_vietnam(now)
    rng = random.Random(RANDOM_SEED)
    keenness = diligence(rng, sorted(buyers))

    courses = {
        course.slug: course
        for course in await session.scalars(select(Course).where(Course.slug.in_(FREE_COURSES)))
    }

    # Free courses are joined first, through the real enrolment, then dated.
    for join in plan_joins(rng, keenness, today):
        if join.course not in courses:
            continue
        user = buyers[join.buyer]
        enrollment, created = await enrollments_service.enrol_free(
            session, courses[join.course].id, user
        )
        if created:
            enrollment.created_at = start_of_day(join.day) + timedelta(hours=rng.randint(7, 22))
            await session.commit()
            written.joined += 1
    # Some of those joins come before the buyer's first purchase, so the
    # account `scripts.seed_sales` dated before that purchase moves back again.
    await backdate_sign_ups(session, list(buyers))
    await session.commit()

    enrollments = (
        await session.execute(
            select(Enrollment, Course.slug)
            .join(Course, Course.id == Enrollment.course_id)
            .where(Enrollment.user_id.in_([user.id for user in buyers.values()]))
            .order_by(Enrollment.created_at)
        )
    ).all()
    emails = {user.id: email for email, user in buyers.items()}
    steps: dict[uuid.UUID, list[Step]] = {}
    actions: list[Action] = []
    for enrollment, slug in enrollments:
        if enrollment.course_id not in steps:
            steps[enrollment.course_id] = await _steps(session, enrollment.course_id)
        email = emails[enrollment.user_id]
        start = enrollment.created_at.astimezone(VIETNAM).date()
        actions += plan_study(
            study_rng(email, slug),
            keenness[email],
            email,
            slug,
            steps[enrollment.course_id],
            start,
            now,
        )

    days: dict[str, set[date]] = defaultdict(set)
    answers: dict[uuid.UUID, tuple[list[int], list[int]]] = {}
    # Ties broken by name, so two sittings in the same minute run in the same
    # order every time.
    for action in sorted(actions, key=lambda a: (a.at, a.buyer, a.course)):
        user = buyers[action.buyer]
        if action.step.quiz_id is None:
            await progress_service.save_position(
                session, action.step.lesson_id, user, last_position_s=0, completed=True
            )
            written.lessons += 1
        else:
            if action.step.quiz_id not in answers:
                answers[action.step.quiz_id] = await _answers(session, action.step.quiz_id)
            right, wrong = answers[action.step.quiz_id]
            attempt, _, _ = await quiz_service.start_attempt(session, action.step.quiz_id, user)
            await quiz_service.submit_attempt(
                session, attempt.id, user, right if action.passes else wrong
            )
            await session.execute(
                update(QuizAttempt)
                .where(QuizAttempt.id == attempt.id)
                .values(started_at=action.at - timedelta(minutes=4), submitted_at=action.at)
            )
            if action.passes:
                written.quizzes_passed += 1
            else:
                written.quizzes_failed += 1
        await _backdate(session, user, action)
        await session.commit()
        days[action.buyer].add(action.at.astimezone(VIETNAM).date())

    # Every action above counted as today; replay the real days in order.
    for email, active in days.items():
        user = buyers[email]
        await session.execute(delete(Streak).where(Streak.user_id == user.id))
        for day in sorted(active):
            await gamification.record_active_day(session, user_id=user.id, day=day)
    await session.commit()

    await leaderboard.rebuild_current(session, leaderboard.get_board(), today=today)
    return written


async def _backdate(session: AsyncSession, user: User, action: Action) -> None:
    """Move what the services stamped with `now()` back to `action.at`.

    Only rows stamped after that moment move: a lesson finished for the second
    time keeps the day it was first finished, exactly as the service would.
    """
    at = action.at
    refs = [action.step.lesson_id] + ([action.step.quiz_id] if action.step.quiz_id else [])
    await session.execute(
        update(XpEvent)
        .where(XpEvent.user_id == user.id, XpEvent.ref_id.in_(refs), XpEvent.created_at > at)
        .values(created_at=at)
    )
    enrollment_ids = select(Enrollment.id).where(Enrollment.user_id == user.id)
    await session.execute(
        update(LessonProgress)
        .where(
            LessonProgress.enrollment_id.in_(enrollment_ids),
            LessonProgress.lesson_id == action.step.lesson_id,
            LessonProgress.completed_at > at,
        )
        .values(completed_at=at, created_at=at, updated_at=at)
    )
    await session.execute(
        update(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.completed_at > at)
        .values(completed_at=at)
    )


async def purge(session: AsyncSession) -> int:
    """Remove what this script writes. Returns how many XP awards went."""
    buyer_ids = select(User.id).where(User.email.in_(buyer_emails()))
    touched = list(
        await session.scalars(
            select(Enrollment.course_id)
            .where(Enrollment.user_id.in_(buyer_ids), Enrollment.source == "free")
            .distinct()
        )
    )
    awards = await session.execute(delete(XpEvent).where(XpEvent.user_id.in_(buyer_ids)))
    # Every course these buyers finished was finished here, so every
    # certificate they hold goes with it.
    await certificates.delete_for_enrollments(
        session, select(Enrollment.id).where(Enrollment.user_id.in_(buyer_ids))
    )
    await session.execute(delete(Streak).where(Streak.user_id.in_(buyer_ids)))
    await session.execute(delete(QuizAttempt).where(QuizAttempt.user_id.in_(buyer_ids)))
    await session.execute(
        delete(LessonProgress).where(
            LessonProgress.enrollment_id.in_(
                select(Enrollment.id).where(Enrollment.user_id.in_(buyer_ids))
            )
        )
    )
    await session.execute(
        delete(Enrollment).where(Enrollment.user_id.in_(buyer_ids), Enrollment.source == "free")
    )
    await session.execute(
        update(Enrollment).where(Enrollment.user_id.in_(buyer_ids)).values(completed_at=None)
    )
    if touched:
        await course_stats.rebuild(session, touched)
    await session.commit()
    await leaderboard.rebuild_current(session, leaderboard.get_board())
    return awards.rowcount or 0


async def _report(session: AsyncSession) -> None:
    today = today_in_vietnam()
    for name, label in (("week", "tuần này"), ("all", "mọi thời gian")):
        period = leaderboard.period_of(name, today)
        statement = (
            select(User.full_name, func.sum(XpEvent.amount).label("xp"))
            .join(User, User.id == XpEvent.user_id)
            .group_by(User.full_name)
            .order_by(func.sum(XpEvent.amount).desc(), User.full_name)
            .limit(3)
        )
        if period.start is not None:
            statement = statement.where(
                XpEvent.created_at >= period.start, XpEvent.created_at < period.end
            )
        top = ", ".join(f"{name_} {xp} XP" for name_, xp in await session.execute(statement))
        print(f"  Dẫn đầu {label}: {top or '(chưa ai)'}")
    # Read through the service, which breaks a streak whose last day was before
    # yesterday: the stored `current_streak` is only true as of that last day.
    buyers = await _buyers(session)
    # By name, so a tie names the same buyer every run.
    summaries = {
        user.full_name: await gamification.get_summary(session, user.id, today=today)
        for user in sorted(buyers.values(), key=lambda user: user.full_name)
    }
    longest = max(summaries.items(), key=lambda item: item[1].longest_streak)
    current = max(summaries.items(), key=lambda item: item[1].current_streak)
    print(f"  Chuỗi dài nhất từng có: {longest[0]} {longest[1].longest_streak} ngày")
    print(f"  Chuỗi đang giữ dài nhất: {current[0]} {current[1].current_streak} ngày")


async def main(purge_first: bool) -> None:
    async with SessionLocal() as session:
        if purge_first:
            awards = await purge(session)
            print(f"Đã gỡ {awards} lần cộng XP cùng tiến độ học của người mua mẫu.")
            return

        if not await _buyers(session):
            print("Chưa có người mua mẫu. Chạy `python -m scripts.seed_sales` trước.")
            return
        written = await seed_study(session)
        if written.lessons == 0 and written.joined == 0:
            print("Dữ liệu học mẫu đã có sẵn. Chạy với --purge để gỡ rồi nạp lại.")
            return
        print(
            f"Đã cho người mua mẫu học {written.lessons} bài, làm {written.quizzes_passed} "
            f"bài trắc nghiệm đạt và {written.quizzes_failed} lần trượt, tham gia thêm "
            f"{written.joined} khóa miễn phí, trong {STUDY_DAYS} ngày gần nhất."
        )
        await _report(session)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--purge", action="store_true", help="gỡ dữ liệu học mẫu")
    asyncio.run(main(parser.parse_args().purge))
