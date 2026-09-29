"""The leaderboard: Redis as a view of `xp_events`, and the page that reads it.

Three promises are tested here. An award reaches the boards **only once its
transaction has committed** -- a rolled-back completion must not leave points
behind in Redis. The boards can always be **rebuilt from the ledger**, and a
read that finds a board missing rebuilds it rather than showing an empty page.
And a Redis outage **costs the leaderboard, never the request**: XP is in
Postgres either way.

Redis is the dictionary in `tests/api/fakes.py` (`memory_board`, autouse).
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, XpEvent
from app.services import gamification, leaderboard
from app.services.leaderboard import period_of
from tests.api.fakes import MemoryLeaderboard
from tests.api.test_gamification import (
    CourseFixture,
    complete,
    make_course,
    make_user,
    sign_in,
    sit_quiz,
)

URL = "/api/v1/leaderboard"


@pytest.fixture
async def course(db_session: AsyncSession) -> CourseFixture:
    return await make_course(db_session, await make_user(db_session, "instructor"))


@pytest.fixture
async def student(db_session: AsyncSession, course: CourseFixture) -> User:
    from app.models import Enrollment

    user = await make_user(db_session)
    db_session.add(Enrollment(user_id=user.id, course_id=course.course.id))
    await db_session.flush()
    return user


def current_keys() -> list[str]:
    today = gamification.today_in_vietnam()
    return [period_of(name, today).key for name in ("week", "month", "all")]


# --- Writing: after the commit, and only then --------------------------------


async def test_finishing_a_lesson_puts_the_student_on_all_three_boards(
    api_client: AsyncClient,
    memory_board: MemoryLeaderboard,
    student: User,
    course: CourseFixture,
) -> None:
    headers = await sign_in(api_client, student)

    await complete(api_client, course.video, headers)

    for key in current_keys():
        assert memory_board.boards[key][str(student.id)] == 10


async def test_a_quiz_pays_the_board_for_the_quiz_and_its_lesson(
    api_client: AsyncClient,
    memory_board: MemoryLeaderboard,
    student: User,
    course: CourseFixture,
) -> None:
    headers = await sign_in(api_client, student)

    await sit_quiz(api_client, course.quiz, headers, [1, 0])
    await sit_quiz(api_client, course.quiz, headers, [1, 0])

    week = current_keys()[0]
    assert memory_board.boards[week][str(student.id)] == 10 + 20


async def test_an_award_is_not_on_the_board_before_its_commit(
    db_session: AsyncSession, memory_board: MemoryLeaderboard, student: User
) -> None:
    await gamification.award(
        db_session, user_id=student.id, reason="lesson_completed", ref_id=uuid.uuid4()
    )

    assert memory_board.boards == {}


async def test_a_rolled_back_award_never_reaches_the_board(
    db_session: AsyncSession, memory_board: MemoryLeaderboard, student: User
) -> None:
    """Staged on the session, and dropped when the transaction is: publishing
    afterwards has nothing to publish."""
    await gamification.award(
        db_session, user_id=student.id, reason="lesson_completed", ref_id=uuid.uuid4()
    )

    await db_session.rollback()
    await leaderboard.publish_awards(db_session)

    assert memory_board.boards == {}


async def test_publishing_twice_does_not_count_twice(
    db_session: AsyncSession, memory_board: MemoryLeaderboard, student: User
) -> None:
    await gamification.award(
        db_session, user_id=student.id, reason="lesson_completed", ref_id=uuid.uuid4()
    )
    await db_session.commit()

    await leaderboard.publish_awards(db_session)
    await leaderboard.publish_awards(db_session)

    assert memory_board.boards[current_keys()[2]][str(student.id)] == 10


async def test_redis_being_down_costs_the_board_not_the_lesson(
    api_client: AsyncClient,
    db_session: AsyncSession,
    memory_board: MemoryLeaderboard,
    student: User,
    course: CourseFixture,
) -> None:
    """The completion and its XP are committed before Redis is touched. A
    failure there is a log line; the nightly rebuild puts the board right."""
    memory_board.fail = True
    headers = await sign_in(api_client, student)

    await complete(api_client, course.video, headers)

    summary = await gamification.get_summary(db_session, student.id)
    assert summary.xp_total == 10


# --- Rebuilding from the ledger ----------------------------------------------


async def ledger_row(session: AsyncSession, user: User, amount: int, at: datetime) -> None:
    session.add(
        XpEvent(
            user_id=user.id,
            amount=amount,
            reason="lesson_completed",
            ref_type="lesson",
            ref_id=uuid.uuid4(),
            created_at=at,
        )
    )
    await session.flush()


async def test_a_rebuild_sums_each_board_over_its_own_period(
    db_session: AsyncSession, memory_board: MemoryLeaderboard, student: User
) -> None:
    """17 September 2026 is a Thursday: the week began on the 14th."""
    await ledger_row(db_session, student, 10, datetime(2026, 9, 16, 3, tzinfo=UTC))
    await ledger_row(db_session, student, 20, datetime(2026, 9, 3, 3, tzinfo=UTC))
    await ledger_row(db_session, student, 30, datetime(2026, 8, 20, 3, tzinfo=UTC))
    # 16:30 UTC on the 13th is 23:30 on Sunday in Hà Nội: last week, this month.
    await ledger_row(db_session, student, 5, datetime(2026, 9, 13, 16, 30, tzinfo=UTC))

    await leaderboard.rebuild_current(db_session, memory_board, today=date(2026, 9, 17))

    me = str(student.id)
    assert memory_board.boards["lb:xp:week:2026-W38"][me] == 10
    assert memory_board.boards["lb:xp:month:2026-09"][me] == 10 + 20 + 5
    assert memory_board.boards["lb:xp:all"][me] == 10 + 20 + 30 + 5
    assert {"lb:xp:week:2026-W38", "lb:xp:month:2026-09", "lb:xp:all"} <= memory_board.built


async def test_a_rebuild_replaces_whatever_drifted(
    db_session: AsyncSession, memory_board: MemoryLeaderboard, student: User
) -> None:
    """Points pushed for a transaction that later turned out not to exist --
    or lost to an outage -- are corrected by the ledger, not added to."""
    today = gamification.today_in_vietnam()
    week = period_of("week", today).key
    memory_board.boards[week] = {str(student.id): 999, "ghost": 50}
    await ledger_row(db_session, student, 10, datetime.now(UTC))

    await leaderboard.rebuild_current(db_session, memory_board, today=today)

    assert memory_board.boards[week][str(student.id)] == 10
    assert "ghost" not in memory_board.boards[week]


# --- Reading -----------------------------------------------------------------


async def seat(board: MemoryLeaderboard, period: str, scores: dict[User, int]) -> None:
    key = period_of(period, gamification.today_in_vietnam()).key
    board.replace(key, {str(user.id): xp for user, xp in scores.items()}, None)


@pytest.fixture
async def four(db_session: AsyncSession) -> dict[str, User]:
    users = {}
    for name in ("An", "Bình", "Chi", "Dũng"):
        user = await make_user(db_session)
        user.full_name = name
        users[name] = user
    await db_session.flush()
    return users


async def test_reading_the_leaderboard_needs_a_sign_in(api_client: AsyncClient) -> None:
    assert (await api_client.get(URL)).status_code == 401


async def test_an_unknown_period_is_refused(api_client: AsyncClient, four: dict[str, User]) -> None:
    headers = await sign_in(api_client, four["An"])

    assert (await api_client.get(f"{URL}?period=year", headers=headers)).status_code == 422


async def test_the_board_ranks_ties_together_and_marks_the_reader(
    api_client: AsyncClient, memory_board: MemoryLeaderboard, four: dict[str, User]
) -> None:
    await seat(
        memory_board,
        "week",
        {four["An"]: 50, four["Bình"]: 40, four["Chi"]: 40, four["Dũng"]: 10},
    )
    headers = await sign_in(api_client, four["Chi"])

    response = await api_client.get(f"{URL}?period=week", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [(row["rank"], row["xp"]) for row in body["items"]] == [
        (1, 50),
        (2, 40),
        (2, 40),
        (4, 10),
    ]
    assert body["items"][0]["user"]["full_name"] == "An"
    assert [row["user"]["full_name"] for row in body["items"] if row["is_me"]] == ["Chi"]
    assert body["me"] == {"rank": 2, "xp": 40}
    assert body["total"] == 4
    assert body["period"] == "week"
    assert body["starts_on"] is not None and body["ends_on"] is not None


async def test_the_reader_s_rank_is_given_even_off_the_page(
    api_client: AsyncClient, memory_board: MemoryLeaderboard, four: dict[str, User]
) -> None:
    await seat(
        memory_board,
        "month",
        {four["An"]: 50, four["Bình"]: 40, four["Chi"]: 30, four["Dũng"]: 10},
    )
    headers = await sign_in(api_client, four["Dũng"])

    body = (await api_client.get(f"{URL}?period=month&page_size=2", headers=headers)).json()

    assert len(body["items"]) == 2
    assert not any(row["is_me"] for row in body["items"])
    assert body["me"] == {"rank": 4, "xp": 10}


async def test_a_second_page_carries_on_the_ranks(
    api_client: AsyncClient, memory_board: MemoryLeaderboard, four: dict[str, User]
) -> None:
    await seat(
        memory_board,
        "all",
        {four["An"]: 50, four["Bình"]: 40, four["Chi"]: 40, four["Dũng"]: 10},
    )
    headers = await sign_in(api_client, four["An"])

    body = (await api_client.get(f"{URL}?period=all&page=2&page_size=2", headers=headers)).json()

    assert [(row["rank"], row["xp"]) for row in body["items"]] == [(2, 40), (4, 10)]
    assert body["starts_on"] is None and body["ends_on"] is None


async def test_somebody_with_no_xp_this_period_has_no_rank(
    api_client: AsyncClient, memory_board: MemoryLeaderboard, four: dict[str, User]
) -> None:
    await seat(memory_board, "week", {four["An"]: 50})
    headers = await sign_in(api_client, four["Bình"])

    body = (await api_client.get(URL, headers=headers)).json()

    assert body["me"] is None
    assert body["period"] == "week"


async def test_a_board_nobody_has_built_is_built_from_the_ledger_on_read(
    api_client: AsyncClient,
    db_session: AsyncSession,
    memory_board: MemoryLeaderboard,
    four: dict[str, User],
) -> None:
    """After a Redis restart the boards are gone while the XP is not. Reading
    one rebuilds it instead of announcing that nobody has studied."""
    await ledger_row(db_session, four["An"], 20, datetime.now(UTC))
    headers = await sign_in(api_client, four["An"])

    body = (await api_client.get(f"{URL}?period=week", headers=headers)).json()

    assert body["me"]["xp"] == 20
    assert current_keys()[0] in memory_board.built


async def test_somebody_deleted_since_the_last_rebuild_is_left_out(
    api_client: AsyncClient, memory_board: MemoryLeaderboard, four: dict[str, User]
) -> None:
    """Deleting a user takes their XP with it, but not their line in Redis
    until the next rebuild. There is no name to show, so the line is skipped."""
    key = period_of("week", gamification.today_in_vietnam()).key
    memory_board.replace(key, {str(uuid.uuid4()): 90, str(four["An"].id): 50}, None)
    headers = await sign_in(api_client, four["An"])

    body = (await api_client.get(URL, headers=headers)).json()

    assert [row["user"]["full_name"] for row in body["items"]] == ["An"]
