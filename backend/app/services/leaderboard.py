"""The XP leaderboard: three Redis sorted sets kept as a view of `xp_events`.

**The ledger is the truth; Redis is a view of it.** Every board can be rebuilt
from `xp_events` at any time (`rebuild_current`, `scripts.rebuild_leaderboard`,
and a Celery beat job every night), so nothing here has to be perfect -- only
never wrong for long.

Three boards, each one sorted set of user id → XP:

* **week** -- an ISO week, Monday to Sunday, in Vietnam: `lb:xp:week:2026-W40`;
* **month** -- a calendar month in Vietnam: `lb:xp:month:2026-09`;
* **all** -- since the beginning: `lb:xp:all`.

**Writing.** `gamification.award` does not touch Redis. It stages what it paid
on the session (`stage`), and whoever commits calls `publish_awards` *after*
the commit -- so a completion that is rolled back never leaves points behind.
A rollback drops what was staged. Publishing is a `ZINCRBY` per board and is
fire-and-forget: a Redis outage is a log line, and the next rebuild puts the
board right.

**Reading.** A board that has never been built from the ledger -- Redis was
restarted, or it is Monday morning and nobody has been paid yet this week --
is built on the spot before it is read. `is_built` asks a marker key that only
a rebuild sets, because a board that exists only through increments may be
missing whatever was paid before Redis last lost it.

One known gap: an increment that lands between a rebuild's query and its
swap is lost until the next rebuild. It is a few points for a few hours, and
closing it would mean locking the ledger against the people earning it.

Redis is used through the **synchronous** client, from a thread
(`asyncio.to_thread`). One client then serves both the API's event loop and
the grading worker, which starts a fresh loop per job -- an asyncio client
would belong to whichever loop created it.
"""

import asyncio
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Protocol

import redis
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.clock import VIETNAM, start_of_day, today_in_vietnam
from app.models import User, XpEvent

logger = logging.getLogger(__name__)

PERIODS = ("week", "month", "all")
KEY_PREFIX = "lb:xp"

# Kept well past the end of the period, so "tuần trước" could still be read
# for a while, and then dropped -- nothing is ever added to an old board.
WEEK_TTL_S = 35 * 86400
MONTH_TTL_S = 400 * 86400

#: Where awards wait on the session between being paid and being committed.
STAGED = "leaderboard.staged"


# --- Periods -----------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    name: str
    key: str
    #: First and last calendar day, inclusive. None for all time.
    starts_on: date | None
    ends_on: date | None
    #: The same bounds as instants, for querying `xp_events.created_at`:
    #: `start <= created_at < end`.
    start: datetime | None
    end: datetime | None
    ttl_s: int | None


def period_of(name: str, day: date) -> Period:
    """The board of kind `name` that `day` (a day in Vietnam) belongs to."""
    if name == "week":
        monday = day - timedelta(days=day.weekday())
        iso = monday.isocalendar()
        sunday = monday + timedelta(days=6)
        return Period(
            name,
            f"{KEY_PREFIX}:week:{iso.year}-W{iso.week:02d}",
            monday,
            sunday,
            start_of_day(monday),
            start_of_day(sunday + timedelta(days=1)),
            WEEK_TTL_S,
        )
    if name == "month":
        first = day.replace(day=1)
        following = (first + timedelta(days=32)).replace(day=1)
        return Period(
            name,
            f"{KEY_PREFIX}:month:{first:%Y-%m}",
            first,
            following - timedelta(days=1),
            start_of_day(first),
            start_of_day(following),
            MONTH_TTL_S,
        )
    if name == "all":
        return Period(name, f"{KEY_PREFIX}:all", None, None, None, None, None)
    raise ValueError(f"unknown leaderboard period: {name!r}")


def periods_for(moment: datetime) -> list[Period]:
    """Every board an award made at `moment` counts towards."""
    day = moment.astimezone(VIETNAM).date()
    return [period_of(name, day) for name in PERIODS]


def rank_rows(rows: Sequence[tuple[str, int]], *, offset: int, above_first: int) -> list[int]:
    """Competition ranks ("1, 2, 2, 4") for one page of a board, highest first.

    `above_first` is how many members score strictly more than the first row
    -- which on any page but the first is not `offset`, if that row is tied
    with the ones before it. After that, a row tied with the previous one
    shares its rank, and a row below it is ranked by its position: everybody
    before it on the board scored more.
    """
    ranks: list[int] = []
    for index, (_, score) in enumerate(rows):
        if index == 0:
            ranks.append(above_first + 1)
        elif score == rows[index - 1][1]:
            ranks.append(ranks[-1])
        else:
            ranks.append(offset + index + 1)
    return ranks


# --- The store -----------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    """One page of a board, and where the reader stands on it."""

    rows: list[tuple[str, int]]
    total: int
    #: Members scoring strictly more than the first row.
    above_first: int
    my_score: int | None
    my_above: int | None


class Board(Protocol):
    """What the leaderboard needs from Redis. Synchronous; see the module doc."""

    def add(self, increments: Sequence[tuple[str, str, int, int | None]]) -> None:
        """(key, member, amount, ttl) -- ZINCRBY each, and keep the key alive."""

    def replace(self, key: str, scores: dict[str, int], ttl: int | None) -> None:
        """Swap a board for these scores in one step, and mark it built."""

    def is_built(self, key: str) -> bool: ...

    def snapshot(self, key: str, offset: int, limit: int, member: str) -> Snapshot: ...


def _built_marker(key: str) -> str:
    return f"{key}:built"


class RedisBoard:
    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    def add(self, increments: Sequence[tuple[str, str, int, int | None]]) -> None:
        pipe = self._redis.pipeline(transaction=False)
        for key, member, amount, ttl in increments:
            pipe.zincrby(key, amount, member)
            if ttl is not None:
                pipe.expire(key, ttl)
        pipe.execute()

    def replace(self, key: str, scores: dict[str, int], ttl: int | None) -> None:
        # Built aside and renamed over the old board, so a reader never sees a
        # half-written one. RENAME is atomic and drops whatever was there.
        pipe = self._redis.pipeline(transaction=True)
        if scores:
            staging = f"{key}:rebuild:{uuid.uuid4().hex}"
            pipe.zadd(staging, scores)
            pipe.rename(staging, key)
            if ttl is not None:
                pipe.expire(key, ttl)
        else:
            pipe.delete(key)
        pipe.set(_built_marker(key), "1", ex=ttl)
        pipe.execute()

    def is_built(self, key: str) -> bool:
        return bool(self._redis.exists(_built_marker(key)))

    def snapshot(self, key: str, offset: int, limit: int, member: str) -> Snapshot:
        pipe = self._redis.pipeline(transaction=False)
        pipe.zrevrange(key, offset, offset + limit - 1, withscores=True)
        pipe.zcard(key)
        pipe.zscore(key, member)
        raw_rows, total, mine = pipe.execute()
        rows = [(name, int(score)) for name, score in raw_rows]

        def above(score: int) -> int:
            return int(self._redis.zcount(key, f"({score}", "+inf"))

        my_score = int(mine) if mine is not None else None
        return Snapshot(
            rows=rows,
            total=int(total),
            above_first=above(rows[0][1]) if rows else 0,
            my_score=my_score,
            my_above=above(my_score) if my_score is not None else None,
        )


@lru_cache
def _shared_board() -> RedisBoard:
    from app.core.config import get_settings

    client = redis.Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        # A leaderboard is not worth a slow request: give up quickly and let
        # the rebuild catch up.
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    return RedisBoard(client)


def get_board() -> Board:
    """The one seam to Redis. Tests replace it (`memory_board` in conftest)."""
    return _shared_board()


# --- Writing -------------------------------------------------------------------


@dataclass(frozen=True)
class Award:
    user_id: uuid.UUID
    amount: int
    at: datetime


def stage(session: AsyncSession, award: Award) -> None:
    """Hold an award until its transaction commits. Called by `gamification`."""
    session.info.setdefault(STAGED, []).append(award)


@event.listens_for(Session, "after_soft_rollback")
def _drop_staged(session: Session, previous_transaction) -> None:
    # Only the session's own transaction ending, not a savepoint inside it:
    # awards staged before the savepoint are still going to be committed.
    if previous_transaction.parent is None:
        session.info.pop(STAGED, None)


async def publish_awards(session: AsyncSession) -> None:
    """Push what the last commit paid to every board it counts towards.

    Call this **after** `commit()`. Never raises: the XP is already safe in
    Postgres, and a board that missed it is corrected by the next rebuild.
    """
    awards: list[Award] = session.info.pop(STAGED, [])
    if not awards:
        return

    increments = [
        (period.key, str(award.user_id), award.amount, period.ttl_s)
        for award in awards
        for period in periods_for(award.at)
    ]
    try:
        await asyncio.to_thread(get_board().add, increments)
    except Exception as exc:  # noqa: BLE001 - see the docstring
        logger.warning("leaderboard not updated for %d award(s): %s", len(awards), exc)


# --- Rebuilding ----------------------------------------------------------------


async def rebuild(session: AsyncSession, board: Board, period: Period) -> int:
    """Replace one board with the sums in the ledger. Returns how many people."""
    statement = select(XpEvent.user_id, func.sum(XpEvent.amount)).group_by(XpEvent.user_id)
    if period.start is not None:
        statement = statement.where(
            XpEvent.created_at >= period.start, XpEvent.created_at < period.end
        )
    scores = {str(user_id): int(total) for user_id, total in await session.execute(statement)}
    await asyncio.to_thread(board.replace, period.key, scores, period.ttl_s)
    return len(scores)


async def rebuild_current(
    session: AsyncSession, board: Board, *, today: date | None = None
) -> dict[str, int]:
    """Rebuild this week's, this month's and the all-time board."""
    today = today or today_in_vietnam()
    return {name: await rebuild(session, board, period_of(name, today)) for name in PERIODS}


# --- Reading -------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    rank: int
    user: User
    xp: int


@dataclass(frozen=True)
class Standings:
    period: Period
    entries: list[Entry]
    total: int
    my_rank: int | None
    my_xp: int | None


async def standings(
    session: AsyncSession,
    viewer: User,
    period_name: str,
    *,
    page: int,
    page_size: int,
    today: date | None = None,
) -> Standings:
    """One page of a board, and the viewer's own place on it.

    A line whose user no longer exists -- deleted since the last rebuild -- is
    left out: there is no name to show. They still count towards the ranks
    below them until the board is rebuilt.
    """
    period = period_of(period_name, today or today_in_vietnam())
    board = get_board()

    if not await asyncio.to_thread(board.is_built, period.key):
        await rebuild(session, board, period)

    snap = await asyncio.to_thread(
        board.snapshot, period.key, (page - 1) * page_size, page_size, str(viewer.id)
    )
    ranks = rank_rows(snap.rows, offset=(page - 1) * page_size, above_first=snap.above_first)

    ids = [uuid.UUID(member) for member, _ in snap.rows]
    users = {user.id: user for user in await session.scalars(select(User).where(User.id.in_(ids)))}
    entries = [
        Entry(rank=rank, user=users[user_id], xp=score)
        for rank, user_id, (_, score) in zip(ranks, ids, snap.rows, strict=True)
        if user_id in users
    ]
    return Standings(
        period=period,
        entries=entries,
        total=snap.total,
        my_rank=snap.my_above + 1 if snap.my_above is not None else None,
        my_xp=snap.my_score,
    )
