"""The leaderboard's arithmetic, without Redis or a database.

Which board an award lands on is a question about calendars -- a week is an ISO
week and a day is a day in Vietnam -- and how a page of scores turns into
ranks is a question about ties. Both are pure, so both are tested here against
explicit dates rather than whatever today happens to be.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.services import leaderboard
from app.services.leaderboard import period_of, periods_for, rank_rows


def test_a_week_runs_monday_to_sunday_in_vietnam() -> None:
    monday = period_of("week", date(2026, 9, 28))
    sunday = period_of("week", date(2026, 10, 4))

    assert monday == sunday
    assert monday.key == "lb:xp:week:2026-W40"
    assert (monday.starts_on, monday.ends_on) == (date(2026, 9, 28), date(2026, 10, 4))
    # Midnight in Hà Nội is five o'clock the evening before in UTC.
    assert monday.start == datetime(2026, 9, 27, 17, tzinfo=UTC)
    assert monday.end == datetime(2026, 10, 4, 17, tzinfo=UTC)


def test_the_first_days_of_january_can_belong_to_last_years_week() -> None:
    """ISO weeks, so the key is the ISO year: 1 January 2027 is a Friday in
    week 53 of 2026, and a key built from the calendar year would split that
    week across two boards."""
    assert period_of("week", date(2027, 1, 1)).key == "lb:xp:week:2026-W53"
    assert period_of("week", date(2026, 12, 28)).key == "lb:xp:week:2026-W53"


def test_a_month_is_a_calendar_month() -> None:
    september = period_of("month", date(2026, 9, 17))

    assert september.key == "lb:xp:month:2026-09"
    assert (september.starts_on, september.ends_on) == (date(2026, 9, 1), date(2026, 9, 30))
    assert september.end == datetime(2026, 9, 30, 17, tzinfo=UTC)


def test_december_ends_where_january_begins() -> None:
    december = period_of("month", date(2026, 12, 5))

    assert december.ends_on == date(2026, 12, 31)
    assert december.end == period_of("month", date(2027, 1, 1)).start


def test_all_time_has_no_bounds_and_never_expires() -> None:
    forever = period_of("all", date(2026, 9, 28))

    assert forever.key == "lb:xp:all"
    assert (forever.start, forever.end, forever.starts_on, forever.ends_on) == (None,) * 4
    assert forever.ttl_s is None


def test_period_boards_expire_after_their_period_is_long_over() -> None:
    """Nothing is added to last week's board, so keeping it forever would be a
    key per week for as long as the platform runs."""
    week = period_of("week", date(2026, 9, 28))
    month = period_of("month", date(2026, 9, 28))

    assert week.ttl_s is not None and week.ttl_s > 7 * 86400
    assert month.ttl_s is not None and month.ttl_s > 31 * 86400


def test_an_unknown_period_is_refused() -> None:
    with pytest.raises(ValueError):
        period_of("year", date(2026, 9, 28))


def test_an_award_just_after_midnight_counts_for_the_new_day() -> None:
    """00:30 on Monday in Hà Nội is still Sunday in UTC. The award belongs to
    the week and the month the student was living in."""
    moment = datetime(2026, 9, 30, 17, 30, tzinfo=UTC)  # 00:30, 1 October, Hà Nội

    keys = [period.key for period in periods_for(moment)]

    assert keys == ["lb:xp:week:2026-W40", "lb:xp:month:2026-10", "lb:xp:all"]


# --- Ranks -------------------------------------------------------------------


def test_equal_scores_share_a_rank_and_the_next_one_skips() -> None:
    """Competition ranking: two people on 40 XP are both second, and whoever
    comes next is fourth -- there were three people ahead of them."""
    rows = [("a", 50), ("b", 40), ("c", 40), ("d", 10)]

    assert rank_rows(rows, offset=0, above_first=0) == [1, 2, 2, 4]


def test_a_page_that_starts_inside_a_tie_keeps_the_tie_s_rank() -> None:
    """Page 2 begins at position 20, but if the first person on it is tied with
    the last three on page 1, they are all 18th -- which only the count of
    scores strictly above can say."""
    rows = [("u", 30), ("v", 30), ("w", 20)]

    assert rank_rows(rows, offset=20, above_first=17) == [18, 18, 23]


def test_an_empty_page_has_no_ranks() -> None:
    assert rank_rows([], offset=0, above_first=0) == []


def test_the_week_key_the_service_writes_is_the_one_it_reads() -> None:
    """Writing and reading build the key through the same function; this pins
    that an award made now is read back by today's board."""
    now = datetime.now(UTC)
    today = leaderboard.today_in_vietnam(now)

    assert periods_for(now)[0].key == period_of("week", today).key
    assert periods_for(now - timedelta(days=7))[0].key != period_of("week", today).key


# --- Against the real thing -------------------------------------------------


@pytest.fixture
def real_redis():
    """A live Redis, or a skip -- except in CI, where it is part of the job.

    The tests above prove the arithmetic against a dictionary; this proves
    the adapter spells ZINCRBY, RENAME and ZCOUNT's exclusive bound the way
    redis-py and Redis expect. `"(40"` versus `"40"` is the difference between
    ties sharing a rank and ties splitting it, and only a real server says
    which one was written.
    """
    import os

    import redis
    from redis.exceptions import RedisError

    from app.core.config import get_settings

    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        client.ping()
    except RedisError as exc:
        client.close()
        if os.getenv("CI"):
            raise
        pytest.skip(f"Redis không chạy ({exc}). `docker compose up -d redis` trong infra/.")
    yield client
    client.close()


def test_the_redis_board_adds_replaces_and_ranks_like_the_rules_say(real_redis) -> None:
    import uuid as uuid_module

    from app.services.leaderboard import RedisBoard

    board = RedisBoard(real_redis)
    key = f"lb:test:{uuid_module.uuid4().hex}"
    try:
        assert board.is_built(key) is False

        board.add([(key, "an", 50, 60), (key, "binh", 30, 60), (key, "chi", 40, 60)])
        board.add([(key, "binh", 10, 60)])  # Bình catches up with Chi.
        assert 0 < real_redis.ttl(key) <= 60

        snap = board.snapshot(key, 0, 10, "chi")
        assert snap.rows[0] == ("an", 50)
        assert sorted(snap.rows[1:]) == [("binh", 40), ("chi", 40)]
        assert snap.total == 3
        # Strictly above 40 is An alone, so Chi is second, tied with Bình.
        assert (snap.my_score, snap.my_above) == (40, 1)
        assert rank_rows(snap.rows, offset=0, above_first=snap.above_first) == [1, 2, 2]

        board.replace(key, {"dung": 70}, 60)
        assert board.is_built(key) is True
        assert board.snapshot(key, 0, 10, "an").rows == [("dung", 70)]
        assert board.snapshot(key, 0, 10, "an").my_score is None

        board.replace(key, {}, 60)
        assert board.snapshot(key, 0, 10, "dung").total == 0
        assert board.is_built(key) is True
    finally:
        real_redis.delete(key, f"{key}:built")
