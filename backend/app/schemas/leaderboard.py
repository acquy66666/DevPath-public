"""The leaderboard as a page reads it."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

LeaderboardPeriod = Literal["week", "month", "all"]


class LeaderboardUserOut(BaseModel):
    """Only what the board shows: a name and a face. No email."""

    id: uuid.UUID
    full_name: str
    avatar_url: str | None


class LeaderboardEntryOut(BaseModel):
    #: Competition ranking: equal XP, equal rank, and the next rank skips.
    rank: int
    user: LeaderboardUserOut
    xp: int
    is_me: bool


class LeaderboardMeOut(BaseModel):
    rank: int
    xp: int


class LeaderboardOut(BaseModel):
    period: LeaderboardPeriod
    #: First and last day of the period, in Vietnam. Null for all time.
    starts_on: date | None
    ends_on: date | None
    items: list[LeaderboardEntryOut]
    total: int
    page: int
    page_size: int
    #: The reader's own place, whether or not it is on this page. Null when
    #: they have earned nothing in this period.
    me: LeaderboardMeOut | None
