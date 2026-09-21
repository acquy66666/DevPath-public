"""Putting the two halves of the recommender together.

`collaborative.py` knows who took what alongside what. `content_based.py`
knows what a course is about. Neither is the recommender the plan asks for --
that one is the blend, and the only real question is *how* to blend.

**Fuse the ranks, not the scores.** Measured on this project's own data
(`docs/report/assets/phase-4/hybrid-blend.txt`):

    collaborative  Σ w·cos   0,0206 … 5,7892   trung bình 0,8192   σ 1,1950
    content-based  cosine    0,7472 … 0,8923   trung bình 0,7989   σ 0,0271

Two things make a weighted sum of those numbers indefensible. They are not on
one scale -- the collaborative score is a *sum* of contributions and grows with
how much history somebody has, while a cosine cannot pass 1. And the
content-based half gives **every** course in the catalogue at least 0,747,
because two Vietnamese course descriptions are never far apart in embedding
space; the collaborative half gives nothing at all to a course no one has taken
alongside anything. Added together, an unrelated course carrying 0,75 of
content score would outrank a course with a real but modest collaborative
signal. What the content-based numbers *do* carry is a usable order -- the
neighbours it finds are right (see the same evidence file) -- so the order is
what this module uses and the numbers are what it throws away.

Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, SIGIR 2009) is the
standard answer to exactly that situation:

    score(course) = Σ  weight(list) / (k + rank in that list)

`k` damps the top of each list so that one list's favourite cannot win on its
own, which is the behaviour a hybrid exists for: a course *both* halves like
should beat a course one half loves and the other has never heard of.

**Weights are equal, and stayed equal once measured.** `scripts/eval_recommender.py`
(`docs/report/assets/phase-4/recommender-eval.txt`) scores every setting on
held-out enrolments and on just-published courses: leaning 2 : 1 towards the
collaborative half keeps new courses out of every top five again (recall@5
0), leaning 1 : 2 towards the content half costs nine points of recall@4 on
the first, and 1 : 1 is the only setting tried that gives up neither.
What the evaluation did change is how much of each list the blend is handed --
see `FUSION_DEPTH`.
"""

import logging
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass

from app.services.collaborative import Recommendation

logger = logging.getLogger(__name__)

#: The names the two halves are known by, in the cache and in the API.
SOURCE_COLLABORATIVE = "collaborative"
SOURCE_CONTENT = "content"
#: Not a ranked list -- popularity is added at serving time to top up a short
#: block, so it never reaches `blend`. Named here because the API reports it
#: alongside the other two and one list of names is better than two.
SOURCE_POPULAR = "popular"

#: The damping constant from the paper, at the value the paper uses.
#:
#: It sets how much better rank 1 is than rank 2: at k=60 that step is worth
#: 1/61 − 1/62 = 0,00026, while the whole gap between rank 1 and rank 20 is
#: 0,0041. Small steps are the point. A smaller k would let whichever list
#: happens to be first decide the top of the block on its own, which is the
#: single-model behaviour the hybrid is meant to replace.
RRF_K = 60

#: How many of each half's list the nightly batch hands to `blend`.
#:
#: Small on purpose, and the one setting here that was measured rather than
#: taken from the paper (`docs/report/assets/phase-4/recommender-eval.md`).
#: The content half gives every course in the catalogue a cosine of at least
#: 0,747, so its list, taken whole, *is* the catalogue -- and then every course
#: the collaborative half names is in both lists and outscores any course in
#: one. A course published today is in one: the content half's. Fed whole
#: (20 each, as before 21/09/2026), it never reached a reader's top 5: recall@5
#: 0,000 on the held-out cold-start test. Cut to 5, a course the content half
#: ranks first can only be beaten by courses in both top-5 lists -- at most
#: four -- and recall@5 is 0,626, while recall on ordinary held-out enrolments
#: moves by no more than the spread between reshuffles.
#:
#: 5 is the smallest depth whose warm recall at every k ≥ 4 stays within that
#: spread of depth 20's; 4 buys a little more cold-start recall and loses two
#: points of recall@10, because the fused list can then hold only eight.
FUSION_DEPTH = 5

#: How much each half counts. Equal, and deliberately so -- see the module
#: docstring for what `eval_recommender.py` measured.
DEFAULT_WEIGHTS: Mapping[str, float] = {
    SOURCE_COLLABORATIVE: 1.0,
    SOURCE_CONTENT: 1.0,
}


@dataclass(frozen=True, slots=True)
class BlendedRecommendation:
    course_id: Hashable
    #: The fused score. Small by nature (around 1/k per list) and comparable
    #: only with other fused scores -- it is a ranking key, not a similarity.
    score: float
    #: A course in the reader's own history, taken from whichever list
    #: contributed most to this candidate. The sentence under the card has to
    #: be the true reason, not an average of two.
    because: Hashable
    #: Every list this candidate appeared in, in a fixed order. Sent to the API
    #: because "cả hai nửa đều gợi ý khóa này" is the claim this whole module
    #: exists to be able to make.
    sources: tuple[str, ...]


def _order(key: Hashable) -> str:
    """A total order over ids of any hashable type, for tie-breaking."""
    return str(key)


def blend(
    sources: Mapping[str, Sequence[Recommendation]],
    *,
    weights: Mapping[str, float] | None = None,
    k: int = RRF_K,
    limit: int,
) -> list[BlendedRecommendation]:
    """Fuse ranked lists into one, best first.

    Each list is read in the order it arrives -- its own model already sorted
    it, and re-sorting here on anything else would quietly disagree with that
    model. Only the position is used.

    A list with no weight given falls back to 1.0 rather than to 0.0: a source
    added later must not vanish because the weights map predates it.

    `limit` is applied **after** fusing: it is the length of the answer, not
    of the inputs. How long each input list is, is the caller's decision --
    the nightly batch hands over `FUSION_DEPTH` from each half, and why that
    is short rather than long is written beside it.
    """
    weights = DEFAULT_WEIGHTS if weights is None else weights

    scores: dict[Hashable, float] = {}
    best: dict[Hashable, tuple[float, Hashable]] = {}
    seen_in: dict[Hashable, set[str]] = {}

    # Sorted, so the `sources` tuples and the arithmetic do not depend on the
    # order a caller happened to build the mapping in.
    for name in sorted(sources):
        weight = weights.get(name, 1.0)
        for rank, recommendation in enumerate(sources[name], start=1):
            course_id = recommendation.course_id
            contribution = weight / (k + rank)

            scores[course_id] = scores.get(course_id, 0.0) + contribution
            seen_in.setdefault(course_id, set()).add(name)

            previous = best.get(course_id)
            if previous is None or contribution > previous[0]:
                best[course_id] = (contribution, recommendation.because)

    ranked = sorted(
        scores.items(),
        # Rounded before comparing, so two candidates equal in meaning are
        # ordered by id rather than by floating-point accident -- the same rule
        # `collaborative.py` uses.
        key=lambda item: (-round(item[1], 12), _order(item[0])),
    )

    return [
        BlendedRecommendation(
            course_id=course_id,
            score=score,
            because=best[course_id][1],
            sources=tuple(sorted(seen_in[course_id])),
        )
        for course_id, score in ranked[:limit]
    ]
