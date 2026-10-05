"""The demo week of questions, notes and reports.

The plan is checked first without a database -- that every person in it can
take part in the course (`seed_interactions` decides enrolments from a fixed
seed, so this is knowable from the plan alone), and that every lesson it names
is one the base seed writes. A wrong line would not corrupt anything, since
every write goes through a service that refuses it; it would stop the script in
front of whoever is preparing the screenshots.

Then the seed runs for real inside a rolled-back transaction, and is read back
through the same services the pages read from.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bookmark, Note, Notification, QaReply, QaThread, Report, User
from app.services import notifications as notifications_service
from app.services import qa as qa_service
from scripts.seed import seed_categories
from scripts.seed_community import (
    COURSE_SLUG,
    INSTRUCTOR,
    SCREENSHOT_LEARNER,
    STUDY,
    THREADS,
    purge,
    seed_community,
)
from scripts.seed_courses import COURSES, seed_courses
from scripts.seed_interactions import build_population, seed_interactions

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


def _lesson_titles() -> set[str]:
    course = next(course for course in COURSES if course.slug == COURSE_SLUG)
    return {lesson.title for section in course.sections for lesson in section.lessons}


def _planned_notes() -> list[str]:
    return [note.content for plan in STUDY for note in plan.notes]


def test_every_lesson_in_the_plan_is_one_the_seed_writes() -> None:
    titles = _lesson_titles()
    for thread in THREADS:
        assert thread.lesson_title in titles, thread.lesson_title
    for plan in STUDY:
        for note in plan.notes:
            assert note.lesson_title in titles, note.lesson_title
        for title in plan.bookmarks:
            assert title in titles, title


def test_every_learner_in_the_plan_is_enrolled_in_the_course() -> None:
    """Q&A admits enrolled learners and the course's staff, nobody else."""
    enrolled = {
        learner.email
        for learner in build_population()
        if any(item.course_slug == COURSE_SLUG for item in learner.items)
    }
    people = set()
    for thread in THREADS:
        people |= {thread.asker, *thread.voters}
        for reply in thread.replies:
            people |= {reply.author, *(email for email, _ in reply.reported_by)}
    people |= {plan.email for plan in STUDY}

    assert people - {INSTRUCTOR} <= enrolled, sorted(people - {INSTRUCTOR} - enrolled)


def test_the_plan_breaks_no_rule_the_services_enforce() -> None:
    for thread in THREADS:
        assert thread.asker not in thread.voters, f"{thread.title}: tự bình chọn"
        for reply in thread.replies:
            for reporter, reason in reply.reported_by:
                assert reporter != reply.author, f"{thread.title}: tự báo cáo"
                assert reason in {"spam", "offensive", "copyright", "misleading"}
            reporters = [email for email, _ in reply.reported_by]
            assert len(reporters) == len(set(reporters)), "một người báo cáo hai lần"


def test_the_inbox_will_have_something_unanswered_and_something_answered() -> None:
    """The instructor's inbox opens on "chưa trả lời"; a demo where that tab is
    empty, or where every question is still waiting, shows half of it."""
    answered = [thread for thread in THREADS if any(r.author == INSTRUCTOR for r in thread.replies)]
    assert answered and len(answered) < len(THREADS)


@pytest.fixture
async def seeded(db_session: AsyncSession) -> None:
    await seed_categories(db_session)
    await seed_courses(db_session)
    await seed_interactions(db_session, build_population())
    # Tests run against the dev database, where the script may already have run
    # for real: start every test from no plan data, inside its transaction.
    await purge(db_session)
    await db_session.flush()


async def _plan_ids(session: AsyncSession) -> tuple[list, list]:
    """(thread ids, reply ids) of the plan's threads as they stand now."""
    titles = [thread.title for thread in THREADS]
    thread_ids = list(await session.scalars(select(QaThread.id).where(QaThread.title.in_(titles))))
    reply_ids = list(
        await session.scalars(select(QaReply.id).where(QaReply.thread_id.in_(thread_ids)))
    )
    return thread_ids, reply_ids


async def _user(session: AsyncSession, email: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


async def test_the_pages_read_back_what_the_seed_wrote(
    db_session: AsyncSession, seeded: None
) -> None:
    await seed_community(db_session, now=NOW)

    instructor = await _user(db_session, INSTRUCTOR)
    learner = await _user(db_session, SCREENSHOT_LEARNER)

    # The instructor's inbox, as /giang-day/hoi-dap opens it.
    unanswered, total = await qa_service.list_for_instructor(
        db_session, instructor, course_id=None, unanswered=True, page=1, page_size=50
    )
    plan_titles = {thread.title for thread in THREADS}
    waiting = {view.thread.title for view in unanswered} & plan_titles
    expected_waiting = {
        thread.title
        for thread in THREADS
        if not any(r.author == INSTRUCTOR for r in thread.replies)
        and thread.resolved_after_minutes is None
    }
    assert waiting == expected_waiting

    # The badge, and the learner's bell.
    answered = next(t for t in THREADS if t.asker == SCREENSHOT_LEARNER)
    view = next(
        v
        for v in (
            await qa_service.list_for_instructor(
                db_session, instructor, course_id=None, unanswered=False, page=1, page_size=50
            )
        )[0]
        if v.thread.title == answered.title
    )
    assert view.has_instructor_reply
    assert view.vote_count == len(answered.voters)
    assert await notifications_service.unread_count(db_session, learner) >= 1

    # The question that was marked solved keeps its own hour, not the seed's.
    solved = next(t for t in THREADS if t.resolved_after_minutes is not None)
    row = await db_session.scalar(select(QaThread).where(QaThread.title == solved.title))
    assert row is not None and row.resolved_at is not None
    asked = NOW - timedelta(hours=solved.hours_ago)
    assert row.created_at == asked
    assert row.resolved_at == asked + timedelta(minutes=solved.resolved_after_minutes)

    # Notes and bookmarks for the screenshot learner.
    notes = await db_session.scalar(
        select(func.count())
        .select_from(Note)
        .where(Note.user_id == learner.id, Note.content.in_(_planned_notes()))
    )
    assert notes == sum(len(plan.notes) for plan in STUDY)
    bookmarks = await db_session.scalar(
        select(func.count()).select_from(Bookmark).where(Bookmark.user_id == learner.id)
    )
    assert bookmarks >= sum(len(plan.bookmarks) for plan in STUDY)

    # The admin's queue: one pending report per reporter of the spam reply.
    _, reply_ids = await _plan_ids(db_session)
    pending = await db_session.scalar(
        select(func.count())
        .select_from(Report)
        .where(Report.status == "open", Report.target_id.in_(reply_ids))
    )
    assert pending == sum(len(r.reported_by) for t in THREADS for r in t.replies)


async def test_notifications_carry_the_hour_of_what_they_announce(
    db_session: AsyncSession, seeded: None
) -> None:
    """A bell saying "vừa xong" under a question asked three days ago would
    give the backdating away."""
    await seed_community(db_session, now=NOW)

    rows = await db_session.execute(
        select(Notification.created_at, QaReply.created_at)
        .join(QaReply, Notification.payload["reply_id"].astext == cast(QaReply.id, String))
        .where(Notification.type == "qa_reply")
    )
    pairs = list(rows)
    assert pairs
    assert all(sent == written for sent, written in pairs)


async def test_running_it_twice_writes_nothing_the_second_time(
    db_session: AsyncSession, seeded: None
) -> None:
    await seed_community(db_session, now=NOW)

    again = await seed_community(db_session, now=NOW)

    assert again.threads == again.replies == again.votes == 0
    assert again.notes == again.bookmarks == again.reports == 0


async def test_purge_takes_back_what_it_wrote_and_what_that_caused(
    db_session: AsyncSession, seeded: None
) -> None:
    """Including the instructor's notifications -- the instructor outlives the
    seeded learners, so nothing else would ever remove them -- and nothing
    that is not the script's: a note the learner wrote by hand stays."""
    await seed_community(db_session, now=NOW)
    thread_ids, reply_ids = await _plan_ids(db_session)
    learner = await _user(db_session, SCREENSHOT_LEARNER)
    by_hand_lesson = await db_session.scalar(
        select(Note.lesson_id).where(Note.user_id == learner.id).limit(1)
    )
    db_session.add(
        Note(user_id=learner.id, lesson_id=by_hand_lesson, timestamp_s=1, content="tự ghi")
    )
    await db_session.flush()

    purged = await purge(db_session)

    assert purged.threads == len(THREADS)
    assert (
        await db_session.scalar(
            select(func.count()).select_from(QaThread).where(QaThread.id.in_(thread_ids))
        )
        == 0
    )
    pointing = await db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.payload["thread_id"].astext.in_([str(i) for i in thread_ids]))
    )
    assert pointing == 0
    reported = await db_session.scalar(
        select(func.count()).select_from(Report).where(Report.target_id.in_(reply_ids))
    )
    assert reported == 0
    notes = list(await db_session.scalars(select(Note.content).where(Note.user_id == learner.id)))
    assert "tự ghi" in notes
    assert not set(notes) & set(_planned_notes())
