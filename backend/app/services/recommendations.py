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
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol

import redis
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from sqlalchemy import case, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Category, Course, Enrollment, User
from app.services.hybrid import SOURCE_POPULAR

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
CACHE_KEY = "rec:v2:user:{user_id}"


@dataclass(frozen=True)
class CachedRecommendation:
    course_id: uuid.UUID
    score: float
    #: A course this user already has, which earned the recommendation.
    because: uuid.UUID
    #: Which halves of the hybrid put it here -- see `services/hybrid.py`.
    #: Stored rather than recomputed because the two models are refitted every
    #: night and this entry is read from for up to two days after that.
    sources: tuple[str, ...] = ()


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
                    "sources": list(item.sources),
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
                sources=tuple(item.get("sources", ())),
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
    #: The fused score from `services/hybrid.py`, or 0.0 for a course the
    #: fallback added -- popularity is not a model score and saying it is one
    #: would put a made-up number in the evidence.
    score: float
    #: The course that earned it, if it can still be named. None when the
    #: reason has since been withdrawn -- the recommendation stands, the
    #: sentence explaining it does not -- and always None for a popular one,
    #: which was earned by nothing the reader did.
    because: Course | None
    #: Which halves chose it, or `("popular",)` for a fallback row.
    sources: tuple[str, ...] = ()


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


async def _history_category_ids(
    session: AsyncSession, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """The categories this reader has already shown up in.

    What "phổ biến theo danh mục" means in practice: somebody whose only
    course is a Python one is better served by the third most popular Python
    course than by the most popular course on the platform. Read from
    enrolments rather than from the cache, because a reader who enrolled this
    morning has a taste the nightly batch has not seen yet.
    """
    rows = await session.scalars(
        select(Course.category_id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user_id)
        .distinct()
    )
    return list(rows)


async def popular_courses(
    session: AsyncSession,
    *,
    limit: int,
    exclude: Collection[uuid.UUID],
    category_ids: Collection[uuid.UUID] = (),
) -> list[tuple[Course, User, Category]]:
    """The catalogue's best-attended courses, the reader's own areas first.

    The fallback the plan asks for, and the only part of this module that
    needs no model at all: `courses.students_count` is denormalised
    (`scripts/rebuild_course_stats.py` recomputes it), so this is one indexed
    read rather than a count over `enrollments`.

    Ordering is by area first and popularity second, which is what makes it a
    *fallback* rather than a second-rate catalogue: a reader with a history
    gets popular courses from the subjects they have shown interest in, and a
    reader with no history at all gets the platform's most popular, because
    `category_ids` is then empty and the first key is constant.
    """
    if limit <= 0:
        return []

    mine = case((Course.category_id.in_(list(category_ids)), 0), else_=1)
    rows = await session.execute(
        select(Course, User, Category)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(
            Course.status == "published",
            Course.deleted_at.is_(None),
            Course.id.notin_(list(exclude)) if exclude else true(),
        )
        # By id last, so two equally popular courses come back in the same
        # order on every request rather than in whatever order the scan found.
        .order_by(
            mine,
            Course.students_count.desc(),
            Course.rating_avg.desc(),
            Course.published_at.desc(),
            Course.id,
        )
        .limit(limit)
    )
    return [(course, instructor, category) for course, instructor, category in rows]


async def for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int,
    cache: RecommendationCache,
) -> ServedRecommendations:
    """This user's cached recommendations, re-checked and topped up.

    The cached order is kept: the scores were fused by the batch and re-sorting
    here on anything else would quietly disagree with it. What changes is only
    which rows survive -- a course that has since been unpublished, withdrawn,
    or enrolled in is dropped.

    Whatever is left is then **topped up with popular courses** until the block
    is full. That is the plan's fallback, and it covers three cases with one
    rule rather than three: a brand-new reader the batch has never seen, a
    reader the model had nothing for, and a reader whose list was cut short by
    the re-check above. Topped-up rows are marked `("popular",)` so the page
    and the evidence can tell them from the model's own.

    `generated_at` still means only one thing -- when a batch last ran for this
    reader -- and stays None for somebody it has never run for, even though
    their block now has courses in it.
    """
    cached = await cache.read(user_id)
    already = await _enrolled_course_ids(session, user_id)
    served: list[ServedRecommendation] = []

    if cached is not None and cached.items:
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
        live = {
            course.id: (course, instructor, category)
            for course, instructor, category in rows
        }

        # The courses quoted as reasons. Looked up without the published
        # filter: the user took them, so naming one is describing their own
        # history.
        reason_ids = {item.because for item in cached.items}
        reasons = {
            course.id: course
            for course in await session.scalars(
                select(Course).where(Course.id.in_(reason_ids))
            )
        }

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
                    sources=item.sources,
                )
            )
            if len(served) == limit:
                break

    if len(served) < limit:
        filler = await popular_courses(
            session,
            limit=limit - len(served),
            exclude=already | {item.course.id for item in served},
            category_ids=await _history_category_ids(session, user_id),
        )
        served.extend(
            ServedRecommendation(
                course=course,
                instructor=instructor,
                category=category,
                # Not a model score, and not dressed up as one.
                score=0.0,
                because=None,
                sources=(SOURCE_POPULAR,),
            )
            for course, instructor, category in filler
        )

    return ServedRecommendations(
        generated_at=cached.generated_at if cached is not None else None,
        items=served,
    )


# --- The nightly batch ------------------------------------------------------


async def rebuild(
    session: AsyncSession,
    writer: RecommendationWriter,
    *,
    top_n: int = DEFAULT_TOP_N,
    embedding_model: str | None = None,
) -> int:
    """Refit both halves, fuse them, and write every user's list. Returns how
    many were written.

    The two models are imported here rather than at module import time so that
    a request, which only ever reads the cache, does not pull them in.

    **Both halves are fitted once and read many times.** The collaborative
    model is built from every enrolment on the platform and the vectors are
    read from `course_embeddings` in one query; after that, each user costs
    arithmetic over what is already in memory. Fitting per user would be the
    same work repeated once per reader.

    `embedding_model` says which vectors count -- rows written by an older
    model are stale and are left out rather than compared against, see
    `content_based.load_vectors`. It defaults to whatever the configuration
    currently names, which is also what the nightly embedding job writes.

    Every user the collaborative model knows gets an entry, including those it
    has nothing for: an empty list with today's timestamp is a fact ("we
    looked"), while leaving yesterday's entry in place would serve
    recommendations the current data no longer supports. Readers with no
    history at all are not written at all -- there is nothing to compute for
    them, and the serving layer answers them with popular courses.
    """
    from app.services.collaborative import fit, load_interactions
    from app.services.content_based import load_vectors, recommend_from_history
    from app.services.hybrid import SOURCE_COLLABORATIVE, SOURCE_CONTENT, blend

    model = fit(await load_interactions(session))
    vectors = await load_vectors(
        session,
        model=embedding_model or get_settings().gemini_embedding_model,
    )
    generated_at = datetime.now(UTC)

    if not vectors:
        # No key, no quota, or the embedding job has never run. The
        # collaborative half still works, and a half-blind recommender is a
        # better answer than an empty block -- but it is worth a line in the
        # log, because nothing else about the output would look wrong.
        logger.warning(
            "Không có vector khóa học nào cho model %s: chỉ dùng nửa collaborative",
            embedding_model or get_settings().gemini_embedding_model,
        )

    written = 0
    for user_id in model.users:
        blended = blend(
            {
                SOURCE_COLLABORATIVE: model.recommend(user_id, k=top_n),
                SOURCE_CONTENT: recommend_from_history(
                    vectors, model.history(user_id), k=top_n
                ),
            },
            limit=top_n,
        )
        writer.write(
            user_id,
            CachedList(
                generated_at=generated_at,
                items=[
                    CachedRecommendation(
                        course_id=item.course_id,
                        score=item.score,
                        because=item.because,
                        sources=item.sources,
                    )
                    for item in blended
                ],
            ),
        )
        written += 1

    logger.info("recommendations rebuilt for %d users", written)
    return written
