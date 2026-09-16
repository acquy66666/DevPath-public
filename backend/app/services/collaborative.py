"""Item-based collaborative filtering over enrolments, completions and ratings.

"People who took the courses you took also took these." The half of the hybrid
recommender that knows nothing about what a course is *about* -- only who took
it alongside what -- and so the half that can recommend across topics the
content-based half would never connect.

**Item-based, not ALS.** The architecture document allows either, and the
choice was made on the data this platform will actually have: tens of users,
not tens of thousands. ALS learns latent factors from a random start, and on a
matrix this small those factors are mostly noise that changes with the seed --
a model nobody can check by hand, and whose output cannot say why. Item-item
cosine over the same matrix is deterministic, every number in it can be worked
out on paper (`tests/test_collaborative.py` does exactly that), and every
recommendation carries the course that earned it. It also needs no compiled
dependency. Whether ALS would score better is a question for
`scripts/eval_recommender.py`, where it can be answered with precision@k
instead of argued.

**How it is computed.** Not as a matrix. For each user, every pair of courses
they have both taken adds `w_a * w_b` to that pair's dot product, and every
course adds `w * w` to its own squared norm; cosine is the ratio. The cost is
the sum over users of (courses per user) squared, which is the number of pairs
that actually co-occur -- a matrix product would pay for every pair of courses
in the catalogue, taken together by anyone or not. Weights are integers, so
the sums are exact and do not depend on the order rows arrived in.
"""

import math
from collections import defaultdict
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, Enrollment, Review

# The implicit-feedback scale from the plan: how strongly an interaction says
# "this person wanted this course".
WEIGHT_ENROLLED = 1
WEIGHT_COMPLETED = 2
WEIGHT_RATED_HIGH = 3

#: At or above this, a rating is the strongest signal there is.
HIGH_RATING = 4
#: At or below this, a rating cancels what a completion would otherwise say.
LOW_RATING = 2

#: Scores are compared rounded to this many places, so two candidates that are
#: equal in meaning but differ in the sixteenth digit are ordered by id rather
#: than by floating-point accident.
SCORE_PRECISION = 12

CourseKey = Hashable
UserKey = Hashable


def interaction_weight(*, completed: bool, rating: int | None) -> int:
    """How strongly one person's history with one course counts.

    **The strongest signal reached, not the sum of the signals.** Every
    completion is also an enrolment, and every review is written by somebody
    enrolled; adding the levels would count the same fact two or three times
    and make the top of a 1-to-3 scale worth 6.

    **A low rating caps the weight at an enrolment.** An implicit matrix has no
    negative entries, so "I finished this and it was bad" cannot pull a course
    away from the ones it was taken with. What it can do is stop counting as the
    strong positive a completion otherwise is -- a 1-star review on a finished
    course reading as "liked it" would be the model misquoting the student.
    A middling rating (3) says neither, and changes nothing.
    """
    if rating is not None and rating <= LOW_RATING:
        return WEIGHT_ENROLLED
    if rating is not None and rating >= HIGH_RATING:
        return WEIGHT_RATED_HIGH
    return WEIGHT_COMPLETED if completed else WEIGHT_ENROLLED


@dataclass(frozen=True)
class Interaction:
    """One person's history with one course, already reduced to a weight."""

    user_id: UserKey
    course_id: CourseKey
    weight: int


@dataclass(frozen=True)
class Recommendation:
    course_id: CourseKey
    score: float
    #: The course in the user's own history that contributed most to this
    #: score -- what a page can quote as "vì bạn đã học ...". Always one the
    #: user has, never inferred.
    because: CourseKey


def _order(key: Hashable) -> str:
    """A total order over ids of any hashable type, for tie-breaking."""
    return str(key)


class ItemModel:
    """Course-to-course similarities, and the histories they were built from.

    Built by `fit`, read by the nightly batch of a later task. Holds only what
    co-occurred: a pair of courses nobody took together has no entry, and
    reads as a similarity of exactly zero.
    """

    def __init__(
        self,
        history: dict[UserKey, dict[CourseKey, int]],
        similar: dict[CourseKey, dict[CourseKey, float]],
    ) -> None:
        self._history = history
        self._similar = similar

    @property
    def users(self) -> list[UserKey]:
        return list(self._history)

    def similarity(self, a: CourseKey, b: CourseKey) -> float:
        return self._similar.get(a, {}).get(b, 0.0)

    def similar_to(self, course_id: CourseKey, k: int) -> list[tuple[CourseKey, float]]:
        """The k courses most often taken alongside this one, most similar first."""
        neighbours = self._similar.get(course_id, {})
        ranked = sorted(
            neighbours.items(),
            key=lambda item: (-round(item[1], SCORE_PRECISION), _order(item[0])),
        )
        return ranked[:k]

    def recommend(self, user_id: UserKey, k: int) -> list[Recommendation]:
        """Up to k courses this user does not have, best first.

        A candidate's score is the sum, over the courses the user has, of
        (how strongly they have it) x (how similar the candidate is to it). A
        plain sum rather than a similarity-weighted average: for ranking, a
        course that several of your courses point at should beat one that a
        single course points at slightly harder.

        Someone with no history gets an empty list. Cold start belongs to the
        hybrid of a later task; answering it here with "popular courses" would
        be a second model hidden inside this one, and the blend would then
        count popularity twice.

        A candidate nothing points at is left out rather than listed at zero --
        a recommendation with no reason behind it is not a recommendation.
        """
        owned = self._history.get(user_id)
        if not owned:
            return []

        scores: dict[CourseKey, float] = defaultdict(float)
        strongest: dict[CourseKey, tuple[CourseKey, float]] = {}

        # Sorted, so the sums and the choice of `because` do not depend on the
        # order the history happened to be loaded in.
        for seen, weight in sorted(owned.items(), key=lambda item: _order(item[0])):
            for candidate, similarity in self._similar.get(seen, {}).items():
                if candidate in owned:
                    continue
                contribution = weight * similarity
                scores[candidate] += contribution
                previous = strongest.get(candidate)
                if previous is None or contribution > previous[1]:
                    strongest[candidate] = (seen, contribution)

        ranked = sorted(
            scores.items(),
            key=lambda item: (-round(item[1], SCORE_PRECISION), _order(item[0])),
        )
        return [
            Recommendation(course_id=course, score=score, because=strongest[course][0])
            for course, score in ranked[:k]
        ]


def fit(interactions: Iterable[Interaction]) -> ItemModel:
    """Build the item-item cosine similarities from a set of interactions.

    The same (user, course) pair may arrive more than once -- the loader joins
    enrolments to reviews, and a caller may merge two sources -- and it is
    kept once, at its strongest. Counting it twice would lengthen that course's
    vector for no reason and shrink every similarity it has.
    """
    history: dict[UserKey, dict[CourseKey, int]] = defaultdict(dict)
    for interaction in interactions:
        courses = history[interaction.user_id]
        courses[interaction.course_id] = max(
            courses.get(interaction.course_id, 0), interaction.weight
        )

    squared_norm: dict[CourseKey, int] = defaultdict(int)
    dot: dict[tuple[CourseKey, CourseKey], int] = defaultdict(int)

    for courses in history.values():
        # Sorted so each unordered pair has exactly one key.
        taken = sorted(courses.items(), key=lambda item: _order(item[0]))
        for index, (a, weight_a) in enumerate(taken):
            squared_norm[a] += weight_a * weight_a
            for b, weight_b in taken[index + 1 :]:
                dot[(a, b)] += weight_a * weight_b

    similar: dict[CourseKey, dict[CourseKey, float]] = defaultdict(dict)
    for (a, b), product in dot.items():
        cosine = product / math.sqrt(squared_norm[a] * squared_norm[b])
        similar[a][b] = cosine
        similar[b][a] = cosine

    return ItemModel(dict(history), dict(similar))


async def load_interactions(session: AsyncSession) -> list[Interaction]:
    """Every enrolment in a course that can currently be recommended.

    One query: enrolments, their completion, and the review the same person
    left on the same course, if any. Starting from enrolments loses nothing --
    the reviews service refuses a review from anyone not enrolled -- and the
    unique constraint on reviews means the join yields one row per enrolment.

    Only published courses that have not been removed. An interaction with a
    withdrawn course still says something about taste, but keeping it in the
    matrix would let that course be recommended, and filtering it back out
    afterwards is a second rule that has to be remembered wherever the model
    is read.
    """
    rows = await session.execute(
        select(
            Enrollment.user_id,
            Enrollment.course_id,
            Enrollment.completed_at,
            Review.rating,
        )
        .join(Course, Course.id == Enrollment.course_id)
        .outerjoin(
            Review,
            and_(
                Review.course_id == Enrollment.course_id,
                Review.user_id == Enrollment.user_id,
            ),
        )
        .where(Course.status == "published", Course.deleted_at.is_(None))
    )
    return [
        Interaction(
            user_id=user_id,
            course_id=course_id,
            weight=interaction_weight(completed=completed_at is not None, rating=rating),
        )
        for user_id, course_id, completed_at, rating in rows
    ]
