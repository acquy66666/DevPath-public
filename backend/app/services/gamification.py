"""XP for finishing things, and a streak for the days somebody studied.

**XP** is paid for three things, each the first time only:

* finishing a lesson (any kind) -- `lesson_completed`;
* passing a quiz -- `quiz_passed`, on top of the lesson it finishes;
* solving a code exercise (an accepted, non-trial submission) --
  `exercise_solved`, likewise on top of its lesson.

"The first time" is `uq_xp_events_ref`, not a check made here: `award` is an
insert that does nothing on conflict, so a lesson unticked and ticked again, a
quiz passed twice or a grading job delivered twice cannot pay out twice.

**A day counts towards the streak** when the student handed something in:
finished a lesson, submitted a quiz, or submitted code (a trial run is a
draft and does not count). Watching does not count either -- the player's
heartbeat would otherwise keep a streak alive from a background tab.

Both need an **enrolment**. An instructor rehearsing their own course is
graded like anybody else, but earns nothing from it.

Nothing here commits: every caller is in the middle of the transaction that
records the thing being rewarded, and XP written separately could survive a
rollback of the completion that justified it.
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import case, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_in_vietnam
from app.models import (
    XP_REASON_REF_TYPES,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Quiz,
    Streak,
    XpEvent,
)
from app.services import leaderboard

#: What each reason is worth. Stored on every event as it is written, so
#: changing a number here changes what that reason pays from now on and leaves
#: everybody's history as it was earned.
XP_AMOUNTS = {
    "lesson_completed": 10,
    "quiz_passed": 20,
    "exercise_solved": 30,
}


async def award(
    session: AsyncSession, *, user_id: uuid.UUID, reason: str, ref_id: uuid.UUID
) -> bool:
    """Pay `reason` for `ref_id`, unless it has been paid already.

    Returns whether this call paid. Does not check the enrolment: the callers
    only get here once a completion has been recorded against one.

    What was paid is staged for the leaderboard, not sent: the caller commits,
    then calls `leaderboard.publish_awards`, so Redis never hears about XP from
    a transaction that was rolled back.
    """
    amount = XP_AMOUNTS[reason]
    statement = (
        insert(XpEvent)
        .values(
            user_id=user_id,
            amount=amount,
            reason=reason,
            ref_type=XP_REASON_REF_TYPES[reason],
            ref_id=ref_id,
        )
        .on_conflict_do_nothing(constraint="uq_xp_events_ref")
        .returning(XpEvent.created_at)
    )
    paid_at = await session.scalar(statement)
    if paid_at is None:
        return False
    leaderboard.stage(session, leaderboard.Award(user_id=user_id, amount=amount, at=paid_at))
    return True


async def record_active_day(session: AsyncSession, *, user_id: uuid.UUID, day: date) -> None:
    """Count `day` towards the streak.

    One statement, so two requests landing at once cannot both read "last
    active yesterday" and both add a day. A day already counted -- or one
    older than the last counted, from a request that straddled midnight --
    changes nothing, which is the `WHERE` on the update.
    """
    yesterday = day - timedelta(days=1)
    continued = case(
        (Streak.last_active_date == yesterday, Streak.current_streak + 1),
        else_=1,
    )
    statement = (
        insert(Streak)
        .values(user_id=user_id, current_streak=1, longest_streak=1, last_active_date=day)
        .on_conflict_do_update(
            constraint="uq_streaks_user_id",
            set_={
                "current_streak": continued,
                "longest_streak": func.greatest(Streak.longest_streak, continued),
                "last_active_date": day,
                "updated_at": func.now(),
            },
            where=Streak.last_active_date < day,
        )
    )
    await session.execute(statement)


async def is_enrolled_in_lesson(
    session: AsyncSession, *, user_id: uuid.UUID, lesson_id: uuid.UUID
) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Lesson.id == lesson_id,
                    CourseSection.id == Lesson.section_id,
                    Enrollment.course_id == CourseSection.course_id,
                    Enrollment.user_id == user_id,
                )
            )
        )
    )


async def record_study(session: AsyncSession, *, user_id: uuid.UUID, lesson_id: uuid.UUID) -> None:
    """Count today for somebody who handed in work on `lesson_id`.

    For the callers that have not already established an enrolment -- a quiz
    or a submission can be reached through a preview lesson, or by the course's
    own instructor.
    """
    if await is_enrolled_in_lesson(session, user_id=user_id, lesson_id=lesson_id):
        await record_active_day(session, user_id=user_id, day=today_in_vietnam())


# --- Reading ----------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    xp_total: int
    current_streak: int
    longest_streak: int
    last_active_date: date | None
    active_today: bool


async def get_summary(
    session: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> Summary:
    """XP so far, and the streak as it stands today.

    The stored streak is what it was on the last active day. Nothing runs at
    midnight to break it, so this is where it breaks: a streak whose last day
    was before yesterday reads as zero. One whose last day was yesterday is
    still alive -- today is not over.
    """
    today = today or today_in_vietnam()

    xp_total = await session.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0)).where(XpEvent.user_id == user_id)
    )
    streak = await session.scalar(select(Streak).where(Streak.user_id == user_id))

    if streak is None:
        return Summary(xp_total, 0, 0, None, False)

    alive = streak.last_active_date >= today - timedelta(days=1)
    return Summary(
        xp_total=xp_total,
        current_streak=streak.current_streak if alive else 0,
        longest_streak=streak.longest_streak,
        last_active_date=streak.last_active_date,
        active_today=streak.last_active_date == today,
    )


@dataclass(frozen=True)
class HistoryItem:
    event: XpEvent
    lesson: Lesson | None
    course: Course | None


async def list_events(
    session: AsyncSession, user_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[HistoryItem], int]:
    """Somebody's XP, newest first, with the lesson each award was for.

    Every reason points at a lesson one way or another -- directly, or through
    the quiz or exercise that sits on it -- and "+20 XP, Kiểm tra chương 1" is
    the line worth showing. A lesson deleted since leaves the award with no
    lesson to name rather than removing it.
    """
    lesson_id = case(
        (XpEvent.ref_type == "lesson", XpEvent.ref_id),
        (
            XpEvent.ref_type == "quiz",
            select(Quiz.lesson_id).where(Quiz.id == XpEvent.ref_id).scalar_subquery(),
        ),
        (
            XpEvent.ref_type == "code_exercise",
            select(CodeExercise.lesson_id)
            .where(CodeExercise.id == XpEvent.ref_id)
            .scalar_subquery(),
        ),
    )

    total = await session.scalar(
        select(func.count()).select_from(XpEvent).where(XpEvent.user_id == user_id)
    )
    rows = await session.execute(
        select(XpEvent, Lesson, Course)
        .select_from(XpEvent)
        .outerjoin(Lesson, Lesson.id == lesson_id)
        .outerjoin(CourseSection, CourseSection.id == Lesson.section_id)
        .outerjoin(Course, Course.id == CourseSection.course_id)
        .where(XpEvent.user_id == user_id)
        .order_by(XpEvent.created_at.desc(), XpEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [HistoryItem(event, lesson, course) for event, lesson, course in rows]
    return items, total or 0
