"""Serving recommendations: computed nightly, kept in Redis, checked on the way out.

The model is not run per request. Fitting item-item similarities reads every
enrolment on the platform, which is fine once a night and absurd on a page
load, so the nightly batch (`app/workers/recommendations.py`) writes each
user's top-N into Redis and this module reads it back.

**What the cache holds is ids, and what the endpoint returns is rows.** The
cache is up to a day stale, and in that day a course can be unpublished,
withdrawn, or -- the common one -- enrolled in by the very person it is being
recommended to. So every cached id is looked up before it is served, and the
three checks are made here rather than trusted to the batch: the batch cannot
know what happens after it runs.

A cache with no entry for someone is different from an entry holding an empty
list. The first means nobody has computed anything for them yet (a new
account, or the batch has never run); the second means it was computed and
there is nothing to suggest. The API says which, because "no recommendations
yet" and "no recommendations for you" are different answers, and the second
one is the hybrid's cue to fall back to popularity in a later task.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol

import redis
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Course, Enrollment, User

logger = logging.getLogger(__name__)

#: How many courses the batch stores per user.
#:
#: More than any page shows, because the checks above remove rows at serving
#: time: a user who enrols in three of their recommendations should not be
#: left with a short list until the next night.
DEFAULT_TOP_N = 20

#: How long a cached list stays usable.
#:
#: Longer than the gap between batches on purpose. If a night is missed --
#: broken beat container, a VPS that was down -- yesterday's recommendations
#: are still better than an empty homepage, and `generated_at` travels with
#: them so the page can tell how old they are.
CACHE_TTL_S = 60 * 60 * 48

#: Versioned: the day the stored shape changes, old entries must not be read
#: as the new one. Bumping this abandons them, and they expire on their own.
CACHE_KEY = "rec:v1:user:{user_id}"


@dataclass(frozen=True)
class CachedRecommendation:
    course_id: uuid.UUID
    score: float
    #: A course this user already has, which earned the recommendation.
    because: uuid.UUID


@dataclass(frozen=True)
class CachedList:
    generated_at: datetime
    items: list[CachedRecommendation]


def dumps(cached: CachedList) -> str:
    return json.dumps(
        {
            "generated_at": cached.generated_at.isoformat(),
            "items": [
                {
                    "course_id": str(item.course_id),
                    "score": item.score,
                    "because": str(item.because),
                }
                for item in cached.items
            ],
        }
    )


def loads(raw: str) -> CachedList:
    payload = json.loads(raw)
    return CachedList(
        generated_at=datetime.fromisoformat(payload["generated_at"]),
        items=[
            CachedRecommendation(
                course_id=uuid.UUID(item["course_id"]),
                score=float(item["score"]),
                because=uuid.UUID(item["because"]),
            )
            for item in payload["items"]
        ],
    )


class RecommendationCache(Protocol):
    """What a request needs: one read. A Protocol so tests can hand over a
    dictionary and exercise the route without Redis."""

    async def read(self, user_id: uuid.UUID) -> CachedList | None: ...


class RecommendationWriter(Protocol):
    """What the nightly batch needs. Synchronous, because the worker is."""

    def write(self, user_id: uuid.UUID, cached: CachedList) -> None: ...


class RedisRecommendationCache:
    def __init__(self, client: aioredis.Redis) -> None:
        self._redis = client

    async def read(self, user_id: uuid.UUID) -> CachedList | None:
        try:
            raw = await self._redis.get(CACHE_KEY.format(user_id=user_id))
        except RedisError as exc:
            # A cache outage is a homepage with no suggestions on it, not an
            # error page. The block this feeds is one section of a page that
            # works without it.
            logger.warning("recommendation cache unavailable: %s", exc)
            return None
        if raw is None:
            return None
        try:
            return loads(raw)
        except (ValueError, KeyError, TypeError) as exc:
            # A key written by an older, incompatible build that shared this
            # version prefix. Read as "nothing cached" rather than a 500.
            logger.warning("unreadable recommendation cache entry: %s", exc)
            return None


class RedisRecommendationWriter:
    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    def write(self, user_id: uuid.UUID, cached: CachedList) -> None:
        self._redis.set(
            CACHE_KEY.format(user_id=user_id), dumps(cached), ex=CACHE_TTL_S
        )


@lru_cache
def _shared_cache() -> RedisRecommendationCache:
    from app.core.config import get_settings

    client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return RedisRecommendationCache(client)


def get_recommendation_cache() -> RecommendationCache:
    """FastAPI dependency. Tests override this; nothing else builds a client."""
    return _shared_cache()


def build_writer() -> RecommendationWriter:
    """The batch's Redis handle. Built per run, in the worker process."""
    from app.core.config import get_settings

    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    return RedisRecommendationWriter(client)


# --- Serving ---------------------------------------------------------------


@dataclass(frozen=True)
class ServedRecommendation:
    course: Course
    instructor: User
    category: Category
    score: float
    #: The course that earned it, if it can still be named. None when the
    #: reason has since been withdrawn -- the recommendation stands, the
    #: sentence explaining it does not.
    because: Course | None


@dataclass(frozen=True)
class ServedRecommendations:
    #: When the batch that produced this ran. None when nothing is cached for
    #: this user at all -- which is not the same as an empty list.
    generated_at: datetime | None
    items: list[ServedRecommendation]

    @property
    def computed(self) -> bool:
        return self.generated_at is not None


async def _enrolled_course_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await session.scalars(
        select(Enrollment.course_id).where(Enrollment.user_id == user_id)
    )
    return set(rows)


async def for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int,
    cache: RecommendationCache,
) -> ServedRecommendations:
    """This user's cached recommendations, re-checked against the database.

    The cached order is kept: the scores were computed by the batch and
    re-sorting here on anything else would quietly disagree with the model.
    What changes is only which rows survive -- a course that has since been
    unpublished, withdrawn, or enrolled in is dropped.
    """
    cached = await cache.read(user_id)
    if cached is None:
        return ServedRecommendations(generated_at=None, items=[])
    if not cached.items:
        return ServedRecommendations(generated_at=cached.generated_at, items=[])

    candidate_ids = [item.course_id for item in cached.items]
    rows = await session.execute(
        select(Course, User, Category)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(
            Course.id.in_(candidate_ids),
            Course.status == "published",
            Course.deleted_at.is_(None),
        )
    )
    live = {course.id: (course, instructor, category) for course, instructor, category in rows}

    already = await _enrolled_course_ids(session, user_id)

    # The courses quoted as reasons. Looked up without the published filter:
    # the user took them, so naming one is describing their own history.
    reason_ids = {item.because for item in cached.items}
    reasons = {
        course.id: course
        for course in await session.scalars(select(Course).where(Course.id.in_(reason_ids)))
    }

    served: list[ServedRecommendation] = []
    for item in cached.items:
        if item.course_id in already or item.course_id not in live:
            continue
        course, instructor, category = live[item.course_id]
        served.append(
            ServedRecommendation(
                course=course,
                instructor=instructor,
                category=category,
                score=item.score,
                because=reasons.get(item.because),
            )
        )
        if len(served) == limit:
            break

    return ServedRecommendations(generated_at=cached.generated_at, items=served)


# --- The nightly batch ------------------------------------------------------


async def rebuild(
    session: AsyncSession,
    writer: RecommendationWriter,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> int:
    """Recompute every user's list from scratch. Returns how many were written.

    Imported here rather than at module import time so that a request, which
    only ever reads the cache, does not pull in the model.

    Every user in the model gets an entry, including those the model has
    nothing for: an empty list with today's timestamp is a fact ("we looked"),
    while leaving yesterday's entry in place would serve recommendations the
    current data no longer supports.
    """
    from app.services.collaborative import fit, load_interactions

    model = fit(await load_interactions(session))
    generated_at = datetime.now(UTC)

    written = 0
    for user_id in model.users:
        writer.write(
            user_id,
            CachedList(
                generated_at=generated_at,
                items=[
                    CachedRecommendation(
                        course_id=recommendation.course_id,
                        score=recommendation.score,
                        because=recommendation.because,
                    )
                    for recommendation in model.recommend(user_id, k=top_n)
                ],
            ),
        )
        written += 1

    logger.info("recommendations rebuilt for %d users", written)
    return written
