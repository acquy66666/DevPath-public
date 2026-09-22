"""Fusing the two halves of the recommender, checked on paper.

No database and no model here: `blend` takes ranked lists and returns a ranked
list, and every number in these tests is worked out by hand from the formula.
That is the point of choosing rank fusion over score fusion -- a blend whose
arithmetic nobody can reproduce is a blend nobody can defend.
"""

import uuid

import pytest

from app.services.collaborative import Recommendation
from app.services.hybrid import (
    RRF_K,
    SOURCE_COLLABORATIVE,
    SOURCE_CONTENT,
    blend,
)

# Readable stand-ins for course ids; `blend` only ever compares and orders them.
A, B, C, D = "khoa-a", "khoa-b", "khoa-c", "khoa-d"
SEEN = "khoa-da-hoc"


def rec(course_id: str, score: float = 1.0, because: str = SEEN) -> Recommendation:
    return Recommendation(course_id=course_id, score=score, because=because)


def rrf(*ranks: int, k: int = RRF_K) -> float:
    """The formula, spelled out: one over (k + rank), summed over the lists."""
    return sum(1.0 / (k + rank) for rank in ranks)


def test_a_course_both_halves_like_beats_a_course_only_one_half_leads() -> None:
    """The whole reason to fuse.

    B is the collaborative list's favourite and appears nowhere else. A is
    second there and third in the content list. Two weak agreements beat one
    strong opinion: 1/62 + 1/63 = 0,032002 against 1/61 = 0,016393.
    """
    blended = blend(
        {
            SOURCE_COLLABORATIVE: [rec(B), rec(A)],
            SOURCE_CONTENT: [rec(C), rec(D), rec(A)],
        },
        limit=10,
    )

    assert [item.course_id for item in blended][:2] == [A, B]
    assert blended[0].score == pytest.approx(rrf(2, 3))
    assert blended[1].score == pytest.approx(rrf(1))


def test_the_score_is_the_sum_of_one_over_k_plus_rank() -> None:
    blended = blend({SOURCE_COLLABORATIVE: [rec(A), rec(B)]}, limit=10)

    assert blended[0].score == pytest.approx(1.0 / (RRF_K + 1))
    assert blended[1].score == pytest.approx(1.0 / (RRF_K + 2))


def test_the_score_ignores_how_big_the_original_numbers_were() -> None:
    """Measured on real data: collaborative scores run 0,02–5,79 while content
    cosines sit between 0,747 and 0,892. Fusing the numbers would let one half
    decide everything; fusing the ranks cannot."""
    huge = blend({SOURCE_COLLABORATIVE: [rec(A, score=5.79), rec(B, score=0.02)]}, limit=10)
    tiny = blend({SOURCE_COLLABORATIVE: [rec(A, score=0.80), rec(B, score=0.79)]}, limit=10)

    assert [item.score for item in huge] == [item.score for item in tiny]


def test_an_item_names_every_list_that_put_it_there() -> None:
    blended = blend(
        {SOURCE_COLLABORATIVE: [rec(A)], SOURCE_CONTENT: [rec(A), rec(B)]},
        limit=10,
    )
    found = {item.course_id: item for item in blended}

    assert found[A].sources == (SOURCE_COLLABORATIVE, SOURCE_CONTENT)
    assert found[B].sources == (SOURCE_CONTENT,)


def test_because_comes_from_the_list_that_contributed_most() -> None:
    """The sentence under the card has to be the true reason, not either one.

    Here the content list ranks A first (1/61) and the collaborative list ranks
    it fifth (1/65), so the course A is shown "because of" is the content
    list's.
    """
    blended = blend(
        {
            SOURCE_COLLABORATIVE: [rec(B), rec(C), rec(D), rec(SEEN), rec(A, because="vi-cf")],
            SOURCE_CONTENT: [rec(A, because="vi-noi-dung")],
        },
        limit=10,
    )

    assert next(item for item in blended if item.course_id == A).because == "vi-noi-dung"


def test_a_weight_of_zero_silences_a_list_without_removing_it() -> None:
    """How `eval_recommender.py` will measure one half against the pair."""
    lists = {SOURCE_COLLABORATIVE: [rec(A), rec(B)], SOURCE_CONTENT: [rec(B), rec(A)]}

    only_cf = blend(lists, weights={SOURCE_COLLABORATIVE: 1.0, SOURCE_CONTENT: 0.0}, limit=10)

    assert [item.course_id for item in only_cf] == [A, B]
    # The silenced list still explains where the candidate was seen.
    assert only_cf[0].sources == (SOURCE_COLLABORATIVE, SOURCE_CONTENT)


def test_weights_move_the_order() -> None:
    lists = {SOURCE_COLLABORATIVE: [rec(A), rec(B)], SOURCE_CONTENT: [rec(B), rec(A)]}

    leaning_content = blend(
        lists, weights={SOURCE_COLLABORATIVE: 1.0, SOURCE_CONTENT: 4.0}, limit=10
    )

    assert [item.course_id for item in leaning_content] == [B, A]


def test_equal_scores_are_ordered_by_id_rather_than_by_accident() -> None:
    """Two lists, mirror images: every candidate scores 1/61 + 1/62. The order
    must still be the same on every machine and every run."""
    blended = blend(
        {SOURCE_COLLABORATIVE: [rec(B), rec(A)], SOURCE_CONTENT: [rec(A), rec(B)]},
        limit=10,
    )

    assert [item.course_id for item in blended] == [A, B]
    assert blended[0].score == pytest.approx(blended[1].score)


def test_nothing_in_means_nothing_out() -> None:
    assert blend({SOURCE_COLLABORATIVE: [], SOURCE_CONTENT: []}, limit=10) == []
    assert blend({}, limit=10) == []


def test_the_limit_is_applied_after_fusing_not_before() -> None:
    """Cutting each list first would drop the agreement that fusion is for."""
    blended = blend(
        {
            SOURCE_COLLABORATIVE: [rec(B), rec(C), rec(A)],
            SOURCE_CONTENT: [rec(D), rec(C), rec(A)],
        },
        limit=1,
    )

    assert [item.course_id for item in blended] == [C]


def test_a_list_nobody_gave_a_weight_for_still_counts() -> None:
    """A source added later must not silently vanish because the weights map
    was written before it existed."""
    blended = blend(
        {SOURCE_COLLABORATIVE: [rec(A)], SOURCE_CONTENT: [rec(B)]},
        weights={SOURCE_COLLABORATIVE: 1.0},
        limit=10,
    )

    assert {item.course_id for item in blended} == {A, B}


def test_course_ids_survive_as_the_type_they_arrived_as() -> None:
    """The batch passes UUIDs; these tests pass strings. Neither is converted."""
    course_id = uuid.uuid4()

    blended = blend({SOURCE_CONTENT: [rec(course_id, because=course_id)]}, limit=10)

    assert blended[0].course_id == course_id
