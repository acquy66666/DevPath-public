"""The demo study plan behind the leaderboard, checked without a database.

The script runs the plan through the real services, so the plan must only ask
for things a student could do: never study in the future, walk a course in
order, finish nothing twice, and retry a quiz that was failed rather than
skip past it. And it must be the same plan on every machine.
"""

import random
import uuid
from datetime import UTC, date, datetime, timedelta

from app.core.clock import VIETNAM
from scripts.seed_study import (
    FREE_COURSES,
    MAX_QUIZ_TRIES,
    STUDY_DAYS,
    Step,
    diligence,
    plan_joins,
    plan_study,
    study_rng,
)

NOW = datetime(2026, 9, 28, 3, 0, tzinfo=UTC)  # 10:00 on a Monday in Hà Nội
TODAY = date(2026, 9, 28)
BUYERS = [f"b{n:02d}" for n in range(40)]
QUIZ = Step(uuid.uuid4(), quiz_id=uuid.uuid4())
COURSE = [Step(uuid.uuid4()) for _ in range(4)] + [QUIZ] + [Step(uuid.uuid4()) for _ in range(5)]


def plans(seed: int = 1) -> list:
    rng = random.Random(seed)
    return [
        plan_study(rng, keen, buyer, "course", COURSE, TODAY - timedelta(days=60), NOW)
        for buyer, keen in diligence(rng, BUYERS).items()
    ]


def test_nobody_studies_in_the_future() -> None:
    for actions in plans():
        assert all(action.at < NOW for action in actions)


def test_the_time_of_day_it_runs_changes_nothing_but_todays_clock() -> None:
    """Run at 07:10 or at 22:00 the same day, the same lessons are studied,
    passed and failed on the same days -- only today's studying is fitted
    into the part of today that has happened."""
    early = datetime(2026, 9, 28, 0, 10, tzinfo=UTC)  # 07:10 in Hà Nội
    late = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)  # 22:00
    # Joined three days ago, so most plans are still going today -- the only
    # day the hour can touch. (The old plan differed in 13 of these 30.)
    start = TODAY - timedelta(days=3)
    studied_today = 0

    for keen in (0.2, 0.6, 0.97):
        for buyer in BUYERS[:10]:
            a = plan_study(study_rng(buyer, "c"), keen, buyer, "c", COURSE, start, early)
            b = plan_study(study_rng(buyer, "c"), keen, buyer, "c", COURSE, start, late)

            assert [(x.step, x.passes) for x in a] == [(x.step, x.passes) for x in b]
            for x, y in zip(a, b, strict=True):
                day = x.at.astimezone(VIETNAM).date()
                assert day == y.at.astimezone(VIETNAM).date()
                if day < TODAY:
                    assert x.at == y.at
            assert all(x.at < early for x in a)
            assert [x.at for x in a] == sorted(x.at for x in a)
            studied_today += any(x.at.astimezone(VIETNAM).date() == TODAY for x in a)

    assert studied_today >= 10, "the case has to reach today to test anything"


def test_the_order_buyers_are_planned_in_changes_nothing() -> None:
    """Two enrolments made in the same second come back from Postgres in
    either order; with a generator per buyer and course, neither order moves
    anybody's plan."""
    start = TODAY - timedelta(days=30)

    def plan_all(order: list[str]) -> dict[str, list]:
        return {
            buyer: [
                (a.step, a.at, a.passes)
                for a in plan_study(study_rng(buyer, "c"), 0.7, buyer, "c", COURSE, start, NOW)
            ]
            for buyer in order
        }

    assert plan_all(BUYERS) == plan_all(list(reversed(BUYERS)))


def test_nothing_is_studied_in_the_first_minutes_after_midnight() -> None:
    just_after = datetime(2026, 9, 27, 17, 2, tzinfo=UTC)  # 00:02 on the 28th
    start = TODAY - timedelta(days=5)
    for buyer in BUYERS[:10]:
        actions = plan_study(study_rng(buyer, "c"), 0.99, buyer, "c", COURSE, start, just_after)
        assert all(a.at < just_after for a in actions)
        assert all(a.at.astimezone(VIETNAM).date() < TODAY for a in actions)


def test_a_course_is_walked_in_order_and_nothing_is_finished_twice() -> None:
    for actions in plans():
        finished = [action.step for action in actions if action.passes]
        assert finished == COURSE[: len(finished)]
        assert [action.at for action in actions] == sorted(action.at for action in actions)


def test_a_failed_quiz_is_sat_again_before_moving_on() -> None:
    failed_somewhere = False
    for actions in plans():
        for index, action in enumerate(actions):
            if action.step == QUIZ and not action.passes:
                failed_somewhere = True
                later = actions[index + 1 :]
                # Either the plan stops here (dropped, or out of days) or the
                # very next thing studied is the same quiz.
                assert not later or later[0].step == QUIZ
    assert failed_somewhere, "the plan should exercise a failed quiz at least once"


def test_a_quiz_is_passed_by_the_last_allowed_try() -> None:
    for actions in plans():
        sittings = [action for action in actions if action.step == QUIZ]
        assert len(sittings) <= MAX_QUIZ_TRIES


def test_studying_starts_after_joining() -> None:
    start = TODAY - timedelta(days=10)
    rng = random.Random(3)
    for keen in (0.1, 0.5, 0.95):
        for action in plan_study(rng, keen, "b", "course", COURSE, start, NOW):
            assert action.at.astimezone(VIETNAM).date() >= start


def test_free_courses_are_joined_at_most_once_each_within_the_window() -> None:
    rng = random.Random(7)
    joins = plan_joins(rng, diligence(rng, BUYERS), TODAY)

    pairs = [(join.buyer, join.course) for join in joins]
    assert len(pairs) == len(set(pairs))
    assert all(join.course in FREE_COURSES for join in joins)
    assert all(TODAY - timedelta(days=STUDY_DAYS) <= join.day < TODAY for join in joins)


def test_the_same_seed_gives_the_same_plan() -> None:
    first = [[(a.step, a.at, a.passes) for a in actions] for actions in plans(5)]
    again = [[(a.step, a.at, a.passes) for a in actions] for actions in plans(5)]

    assert first == again
