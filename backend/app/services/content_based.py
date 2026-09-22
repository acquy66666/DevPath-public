"""The content-based half of the hybrid recommender.

Item-based collaborative filtering (`services/collaborative.py`) knows who took
what alongside what, and nothing about what a course is *about*. That is enough
once a catalogue has a history behind it, and useless on the day a course is
published: nobody has taken it, so nothing is similar to it and it is similar
to nothing. This module answers the same question from the words instead --
title, subtitle, category and description, embedded once and compared by
cosine -- which is what makes "Khóa học tương tự" work on a course page from
the hour it goes on sale.

**One vector per course, not per chunk.** The RAG side cuts lessons into
passages because a question is answered by one passage; here the unit being
compared *is* the course, and a course whose lessons each had their own vector
would have no single point to measure from. The text is short enough to embed
whole, which also means re-embedding one course is one call.

**`SEMANTIC_SIMILARITY`, not `RETRIEVAL_DOCUMENT`.** Both sides of this
comparison are the same kind of thing -- a course description against another
course description -- while retrieval embeddings are trained for the asymmetric
case of a short question against a long passage. The adapter exposes the task
type; using the wrong one costs ranking quality and shows up as nothing more
specific than "the similar courses are a bit odd".

**Unpublishing does not delete the vector**, for the same reason unpublishing
does not delete `doc_chunks`: publishing again would pay for the embedding a
second time. Keeping a withdrawn course out of the results is the query's job
below, not the job of whatever changed the status.
"""

import logging
import math
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Course, CourseEmbedding, Enrollment, User
from app.services.chunking import CHARS_PER_TOKEN
from app.services.collaborative import SCORE_PRECISION, Recommendation
from app.services.courses import CourseNotFoundError

logger = logging.getLogger(__name__)

#: How much of a course description is worth embedding.
#:
#: Well under `gemini-embedding-001`'s 2048-token input limit, which it
#: truncates past without an error -- a half-embedded course would sit in the
#: table looking exactly like a whole one. The margin absorbs the known 2.5%
#: under-count in `CHARS_PER_TOKEN` (docs/report/assets/phase-4/
#: token-estimate.txt) several times over.
#:
#: It is also a quality decision, not only a safety one: a course's own summary
#: says what it is about in its first paragraphs, and the syllabus, the refund
#: policy and the instructor's biography that follow would dilute the vector
#: with words every course on the platform shares.
MAX_SOURCE_TOKENS = 1000
MAX_SOURCE_CHARS = int(MAX_SOURCE_TOKENS * CHARS_PER_TOKEN)


def course_text(course: Course, category_name: str) -> str:
    """The words this course is embedded as.

    The heading -- title, subtitle, category -- is never dropped: it is the
    part that names the subject, and two courses on the same topic are far more
    likely to share it than to share a sentence of prose. Only the description
    is cut, and only at a space, because a truncated word is a token the model
    has never seen.
    """
    heading = "\n".join(
        part.strip()
        for part in (course.title, course.subtitle, f"Danh mục: {category_name}")
        if part and part.strip()
    )[:MAX_SOURCE_CHARS]

    description = (course.description or "").strip()
    room = MAX_SOURCE_CHARS - len(heading) - len("\n\n")
    if not description or room <= 0:
        return heading.strip()

    if len(description) > room:
        description = _cut_at_word(description, room)
    return f"{heading}\n\n{description}".strip()


def _cut_at_word(text: str, room: int) -> str:
    """At most `room` characters of `text`, ending where a word does.

    A stretch of `room` characters with no whitespace anywhere in it is cut
    where it falls -- there is nothing better to do, and prose that shape is
    not prose.
    """
    cut = text[:room]
    spaced = cut.rsplit(None, 1)[0] if len(cut.split()) > 1 else cut
    return spaced.strip()


# --- Filling the table ------------------------------------------------------


class SimilarityEmbedder(Protocol):
    """What a rebuild depends on -- narrower than `llm.Embedder` on purpose.

    The RAG side needs two task types because retrieval is asymmetric; this
    side needs exactly one, and a Protocol that asked for the other two would
    make every fake in these tests implement methods the code never calls.
    """

    @property
    def model(self) -> str:
        """Recorded per row in `course_embeddings.embedding_model`."""

    async def embed_similarity(self, texts: Sequence[str]) -> list[list[float]]: ...


#: Courses embedded, and committed, per round.
#:
#: A key that runs out partway through is the expected failure here, not the
#: exceptional one, so the run commits as it goes -- like the lesson ingest,
#: which commits per lesson. Everything already written reads as `unchanged`
#: on the next attempt, which is what makes re-running after a quota reset
#: cheap instead of a second full bill.
REBUILD_BATCH = 20


@dataclass(frozen=True, slots=True)
class EmbeddingReport:
    """What one rebuild did. Printed by the script, logged by the worker."""

    #: Courses whose vector was written or rewritten -- what was paid for.
    embedded: int
    #: Courses already embedded from the same words by the same model.
    unchanged: int


async def rebuild_embeddings(
    session: AsyncSession,
    *,
    embedder: SimilarityEmbedder,
    course_ids: Iterable[uuid.UUID] | None = None,
) -> EmbeddingReport:
    """Embed every publishable course whose text or model has changed.

    `course_ids` narrows it to the course that was just published; without it
    the whole catalogue is checked, which is what the nightly run does and what
    catches a course edited without being republished.

    Only published, undeleted courses: an embedding exists to be compared
    against, and nothing else can appear on either side of a comparison. A
    course that *loses* that status keeps its row -- see the module docstring.

    Raises whatever the embedder raises. Courses committed before that point
    stay committed.
    """
    query = (
        select(Course, Category.name)
        .join(Category, Category.id == Course.category_id)
        .where(Course.status == "published", Course.deleted_at.is_(None))
        .order_by(Course.created_at, Course.id)
    )
    if course_ids is not None:
        wanted = list(course_ids)
        if not wanted:
            return EmbeddingReport(embedded=0, unchanged=0)
        query = query.where(Course.id.in_(wanted))

    rows = (await session.execute(query)).all()
    if not rows:
        return EmbeddingReport(embedded=0, unchanged=0)

    existing = {
        row.course_id: row
        for row in await session.scalars(
            select(CourseEmbedding).where(
                CourseEmbedding.course_id.in_([course.id for course, _ in rows])
            )
        )
    }

    pending: list[tuple[Course, str]] = []
    unchanged = 0
    for course, category_name in rows:
        text = course_text(course, category_name)
        row = existing.get(course.id)
        if (
            row is not None
            and row.source_text == text
            and row.embedding_model == embedder.model
        ):
            unchanged += 1
            continue
        pending.append((course, text))

    embedded = 0
    for start in range(0, len(pending), REBUILD_BATCH):
        batch = pending[start : start + REBUILD_BATCH]
        vectors = await embedder.embed_similarity([text for _, text in batch])
        for (course, text), vector in zip(batch, vectors, strict=True):
            row = existing.get(course.id)
            if row is None:
                session.add(
                    CourseEmbedding(
                        course_id=course.id,
                        source_text=text,
                        embedding=vector,
                        embedding_model=embedder.model,
                    )
                )
            else:
                row.source_text = text
                row.embedding = vector
                row.embedding_model = embedder.model
        await session.commit()
        embedded += len(batch)

    logger.info(
        "Nhúng khóa học: %d khóa mới nhúng, %d khóa không đổi", embedded, unchanged
    )
    return EmbeddingReport(embedded=embedded, unchanged=unchanged)


# --- Reading it back --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SimilarCourse:
    """One neighbour, with everything a card needs and the number behind it."""

    course: Course
    instructor: User
    category: Category
    #: Cosine similarity with the course being viewed, 1.0 being identical.
    #: Sent to the client because the thesis evaluates this ranking, and a
    #: ranking whose numbers never leave the server cannot be checked against
    #: what the page actually showed.
    score: float


async def similar_to(
    session: AsyncSession,
    *,
    course_id: uuid.UUID,
    limit: int,
    skip_enrolled_by: uuid.UUID | None = None,
) -> list[SimilarCourse]:
    """The published courses nearest this one, nearest first.

    One query against the vector index, with the visibility rules inside it
    rather than applied afterwards -- the same decision the chat retrieval
    made, and for the same reason: a filter applied after a `LIMIT` returns
    fewer rows than asked for and looks like a short catalogue.

    (pgvector applies a `WHERE` *after* the HNSW scan has picked its
    candidates, so on a large catalogue a very selective filter can still
    under-return. Not reachable here yet -- at two dozen rows Postgres
    sequential-scans -- but it is the thing to measure before this table
    reaches thousands of courses, not after.)

    Raises `CourseNotFoundError` for a course the public cannot see. The block
    lives on the public course page, so a draft has no answer here -- and an
    empty list would read as "nothing is similar to this", which is a
    different claim.

    Returns an empty list when the course has no vector yet: published a
    minute ago, batch not run. The page shows no block, which is the right
    answer to "we have not worked it out yet".

    `skip_enrolled_by` is "Học tiếp theo": the same neighbours, less the
    courses that reader already has. Inside the query for the reason above --
    a reader who took the three nearest courses would otherwise get an empty
    block from a `LIMIT 3` while the fourth-nearest went unmentioned.
    """
    target = await session.scalar(
        select(CourseEmbedding)
        .join(Course, Course.id == CourseEmbedding.course_id)
        .where(
            CourseEmbedding.course_id == course_id,
            Course.status == "published",
            Course.deleted_at.is_(None),
        )
    )
    if target is None:
        # Either the course cannot be shown, or it can and has no vector. The
        # two are told apart by asking again without the embedding.
        visible = await session.scalar(
            select(Course.id).where(
                Course.id == course_id,
                Course.status == "published",
                Course.deleted_at.is_(None),
            )
        )
        if visible is None:
            raise CourseNotFoundError("Không tìm thấy khóa học")
        return []

    distance = CourseEmbedding.embedding.cosine_distance(target.embedding)
    rows = await session.execute(
        select(Course, User, Category, distance.label("distance"))
        .join(CourseEmbedding, CourseEmbedding.course_id == Course.id)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(
            Course.id != course_id,
            Course.status == "published",
            Course.deleted_at.is_(None),
            # A distance between two models' vectors is a number with no
            # meaning -- see `CourseEmbedding.embedding_model`.
            CourseEmbedding.embedding_model == target.embedding_model,
            Course.id.notin_(
                select(Enrollment.course_id).where(
                    Enrollment.user_id == skip_enrolled_by
                )
            )
            if skip_enrolled_by is not None
            else true(),
        )
        # By id as well, so two courses at the same distance come back in the
        # same order every time rather than in whatever order the scan found.
        .order_by(distance, Course.id)
        .limit(limit)
    )

    return [
        SimilarCourse(
            course=course,
            instructor=instructor,
            category=category,
            score=1.0 - float(distance_value),
        )
        for course, instructor, category, distance_value in rows
    ]


# --- Recommending from a history --------------------------------------------


@dataclass(frozen=True, slots=True)
class CourseVector:
    """One course's point, without the row around it.

    `similar_to` above answers one course page and returns everything a card
    needs; this is what the nightly batch reads instead, because it compares
    every reader's history against the whole catalogue and has no use for
    titles. A few thousand courses is a few megabytes of floats -- small
    enough to hold, and far cheaper than a query per reader per course.
    """

    course_id: uuid.UUID
    embedding: Sequence[float]


async def load_vectors(session: AsyncSession, *, model: str) -> list[CourseVector]:
    """Every recommendable course's vector, for one embedding model.

    The model is named by the caller rather than inferred from the rows: it is
    whatever `GEMINI_EMBEDDING_MODEL` currently says, which is also what the
    nightly embedding job writes. Rows left behind by an older model are stale
    and stay out of the arithmetic until they are rebuilt -- comparing across
    models returns nonsense rather than an error.
    """
    rows = await session.execute(
        select(CourseEmbedding.course_id, CourseEmbedding.embedding)
        .join(Course, Course.id == CourseEmbedding.course_id)
        .where(
            Course.status == "published",
            Course.deleted_at.is_(None),
            CourseEmbedding.embedding_model == model,
        )
        .order_by(CourseEmbedding.course_id)
    )
    return [CourseVector(course_id=course_id, embedding=embedding) for course_id, embedding in rows]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Proper cosine, not a dot product.

    The vectors were unit length when they were written, but they make a round
    trip through pgvector's float4 storage, and these numbers end up in
    evidence files that are checked by hand. Dividing by the norms costs
    nothing here and removes a whole class of "why is it 0,9999".
    """
    dot = norm_left = norm_right = 0.0
    for a, b in zip(left, right, strict=True):
        dot += a * b
        norm_left += a * a
        norm_right += b * b
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / math.sqrt(norm_left * norm_right)


def recommend_from_history(
    vectors: Sequence[CourseVector],
    history: Mapping[uuid.UUID, int],
    *,
    k: int,
) -> list[Recommendation]:
    """Courses closest to what this reader already has, best first.

    Built to the same shape as `collaborative.ItemModel.recommend`, so the two
    lists can be fused without either being reinterpreted:

    * a candidate's score is the sum, over the reader's courses, of (how
      strongly they have it) × (how similar the candidate is to it). A plain
      sum rather than an average: a course that several of the reader's
      courses point at should beat one that a single course points at slightly
      harder.
    * `because` is the single course that contributed most -- always one the
      reader has, never inferred.
    * a reader with no history gets an empty list. Cold start is the serving
      layer's popularity fallback, not a second model hidden in this one.
    * a candidate nothing points at is left out rather than listed at zero.

    Courses in `history` with no vector are skipped: published since the last
    embedding run, or embedded by a model this catalogue has moved off.
    """
    known = {vector.course_id: vector.embedding for vector in vectors}
    owned = {
        course_id: weight
        for course_id, weight in history.items()
        if course_id in known
    }
    if not owned:
        return []

    scores: dict[uuid.UUID, float] = defaultdict(float)
    strongest: dict[uuid.UUID, tuple[uuid.UUID, float]] = {}

    # Sorted, so the sums and the choice of `because` do not depend on the
    # order the history happened to be loaded in.
    for seen in sorted(owned, key=str):
        weight = owned[seen]
        for candidate in vectors:
            if candidate.course_id in history:
                continue
            similarity = _cosine(known[seen], candidate.embedding)
            if similarity <= 0:
                # No reason behind it, so not a recommendation.
                continue
            contribution = weight * similarity
            scores[candidate.course_id] += contribution
            previous = strongest.get(candidate.course_id)
            if previous is None or contribution > previous[1]:
                strongest[candidate.course_id] = (seen, contribution)

    ranked = sorted(
        scores.items(),
        key=lambda item: (-round(item[1], SCORE_PRECISION), str(item[0])),
    )
    return [
        Recommendation(course_id=course_id, score=score, because=strongest[course_id][0])
        for course_id, score in ranked[:k]
    ]
