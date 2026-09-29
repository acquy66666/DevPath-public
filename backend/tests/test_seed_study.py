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
