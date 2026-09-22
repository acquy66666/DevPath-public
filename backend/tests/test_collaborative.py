"""Item-based collaborative filtering, checked against numbers worked out by hand.

No database here. The model is arithmetic over (user, course, weight) triples,
so it is tested as arithmetic: every expected similarity and score below can
be recomputed on paper from the fixture, and a test that fails is wrong by an
amount that means something.

The fixture most tests share:

    user   x   y   z
    A      3   3   .
    B      1   .   2
    C      .   1   1

    |x| = sqrt(9 + 1) = sqrt(10)
    |y| = sqrt(9 + 1) = sqrt(10)
    |z| = sqrt(4 + 1) = sqrt(5)

    sim(x, y) = (3*3)     / (sqrt10 * sqrt10) = 9 / 10      = 0.9
    sim(x, z) = (1*2)     / (sqrt10 * sqrt5)  = 2 / sqrt(50) = 0.28284...
    sim(y, z) = (1*1)     / (sqrt10 * sqrt5)  = 1 / sqrt(50) = 0.14142...
"""

import math

import pytest

from app.services.collaborative import (
    WEIGHT_COMPLETED,
    WEIGHT_ENROLLED,
    WEIGHT_RATED_HIGH,
    Interaction,
    fit,
    interaction_weight,
)

SIM_XY = 0.9
SIM_XZ = 2 / math.sqrt(50)
SIM_YZ = 1 / math.sqrt(50)


def triples(*rows: tuple[str, str, int]) -> list[Interaction]:
    return [Interaction(user_id=u, course_id=c, weight=w) for u, c, w in rows]


@pytest.fixture
def interactions() -> list[Interaction]:
    return triples(
        ("A", "x", 3),
        ("A", "y", 3),
        ("B", "x", 1),
        ("B", "z", 2),
        ("C", "y", 1),
        ("C", "z", 1),
    )


# --- How strong an interaction is -----------------------------------------


def test_the_three_levels_are_the_ones_the_plan_names():
    assert (WEIGHT_ENROLLED, WEIGHT_COMPLETED, WEIGHT_RATED_HIGH) == (1, 2, 3)


def test_the_strongest_signal_wins_rather_than_the_sum():
    """Every completion is also an enrolment. Adding them counts one fact twice,
    and would make "finished it and loved it" worth 6 on a scale meant to top
    out at 3."""
    assert interaction_weight(completed=False, rating=None) == 1
    assert interaction_weight(completed=True, rating=None) == 2
    assert interaction_weight(completed=True, rating=5) == 3
    assert interaction_weight(completed=False, rating=4) == 3


def test_a_middling_rating_neither_raises_nor_lowers_the_weight():
    assert interaction_weight(completed=True, rating=3) == 2
    assert interaction_weight(completed=False, rating=3) == 1


def test_a_low_rating_is_not_read_as_liking_the_course():
    """An implicit matrix has no negative numbers, so "I finished it and it was
    bad" cannot go below zero. What it can do is stop counting as the strong
    signal a completion otherwise is."""
    assert interaction_weight(completed=True, rating=1) == 1
    assert interaction_weight(completed=True, rating=2) == 1


# --- Item similarity --------------------------------------------------------


def test_similarity_is_cosine_over_the_weighted_vectors(interactions):
    model = fit(interactions)

    assert model.similarity("x", "y") == pytest.approx(SIM_XY)
    assert model.similarity("x", "z") == pytest.approx(SIM_XZ)
    assert model.similarity("y", "z") == pytest.approx(SIM_YZ)


def test_similarity_is_symmetric(interactions):
    model = fit(interactions)
    assert model.similarity("z", "x") == model.similarity("x", "z")


def test_courses_nobody_took_together_are_not_similar_at_all():
    model = fit(triples(("A", "x", 1), ("B", "y", 1)))
    assert model.similarity("x", "y") == 0.0


def test_a_course_is_not_listed_as_similar_to_itself(interactions):
    assert "x" not in [course for course, _ in model_similar(interactions, "x")]


def model_similar(interactions: list[Interaction], course: str) -> list[tuple[str, float]]:
    return fit(interactions).similar_to(course, k=10)


def test_similar_courses_come_most_similar_first(interactions):
    ranked = model_similar(interactions, "x")
    assert [course for course, _ in ranked] == ["y", "z"]
    assert [score for _, score in ranked] == pytest.approx([SIM_XY, SIM_XZ])


def test_the_same_pair_seen_twice_is_one_interaction_at_its_strongest():
    """The loader can produce duplicates -- an enrolment row and a review row
    for the same person and course. Two rows must not double the vector."""
    once = fit(triples(("A", "x", 3), ("A", "y", 3), ("B", "x", 1), ("B", "y", 2)))
    twice = fit(
        triples(("A", "x", 1), ("A", "x", 3), ("A", "y", 3), ("B", "x", 1), ("B", "y", 2))
    )
    assert twice.similarity("x", "y") == pytest.approx(once.similarity("x", "y"))


# --- Recommending -----------------------------------------------------------


def test_the_score_is_the_weighted_sum_over_what_the_user_has(interactions):
    """D has taken x at weight 2.

    D is part of the data the model is fitted on, so x's vector gains D's entry
    and the fixture's similarities no longer hold -- which is right: a user's
    own history is evidence too. With D in, |x|^2 = 9 + 1 + 4 = 14:

        sim(x, y) = 9 / sqrt(14 * 10)   ->  y scores 2 * 9 / sqrt(140)
        sim(x, z) = 2 / sqrt(14 * 5)    ->  z scores 2 * 2 / sqrt(70)
    """
    model = fit([*interactions, *triples(("D", "x", 2))])

    recommended = model.recommend("D", k=10)

    assert [r.course_id for r in recommended] == ["y", "z"]
    assert [r.score for r in recommended] == pytest.approx(
        [2 * 9 / math.sqrt(140), 2 * 2 / math.sqrt(70)]
    )


def test_evidence_from_several_courses_adds_up(interactions):
    """E has x and y at weight 1; z's score is one contribution from each.

    With E in the data, |x|^2 = |y|^2 = 11 and |z|^2 = 5:

        sim(x, z) = 2 / sqrt(55),  sim(y, z) = 1 / sqrt(55)
        z scores 1 * 2 / sqrt(55) + 1 * 1 / sqrt(55) = 3 / sqrt(55)
    """
    model = fit([*interactions, *triples(("E", "x", 1), ("E", "y", 1))])

    [only] = model.recommend("E", k=10)

    assert only.course_id == "z"
    assert only.score == pytest.approx(3 / math.sqrt(55))


def test_each_recommendation_names_the_course_that_earned_it(interactions):
    """The course that contributed most -- what "vì bạn đã học ..." will quote.

    For E, z's score is 2 / sqrt(55) from x and 1 / sqrt(55) from y (see the
    test above), so the reason is x.
    """
    model = fit([*interactions, *triples(("E", "x", 1), ("E", "y", 1))])

    [only] = model.recommend("E", k=10)

    assert only.because == "x"


def test_courses_the_user_already_has_are_never_recommended(interactions):
    recommended = fit(interactions).recommend("A", k=10)
    assert {r.course_id for r in recommended}.isdisjoint({"x", "y"})


def test_a_course_with_no_evidence_is_left_out_rather_than_scored_zero():
    """F took x; w is only ever taken alone, so nothing links it to x. A zero
    at the bottom of the list is a recommendation with no reason behind it."""
    model = fit(triples(("A", "x", 1), ("A", "y", 1), ("B", "w", 1), ("F", "x", 1)))

    assert [r.course_id for r in model.recommend("F", k=10)] == ["y"]


def test_k_cuts_the_list(interactions):
    model = fit([*interactions, *triples(("D", "x", 2))])
    assert [r.course_id for r in model.recommend("D", k=1)] == ["y"]


def test_someone_with_no_history_gets_nothing_from_this_model(interactions):
    """Cold start is the hybrid's job, not this one's.

    Returning "popular courses" from here would be a second model hiding inside
    the first, and the blend in the next task would then count popularity twice.
    """
    assert fit(interactions).recommend("stranger", k=10) == []


def test_ties_come_out_in_the_same_order_every_time():
    """Two candidates with identical scores. Without a tie-break the order
    depends on dict iteration, and a nightly batch would reshuffle a user's
    list for no reason."""
    rows = triples(
        ("A", "x", 1), ("A", "p", 1),
        ("B", "x", 1), ("B", "q", 1),
        ("U", "x", 1),
    )  # fmt: skip
    first = [r.course_id for r in fit(rows).recommend("U", k=10)]
    again = [r.course_id for r in fit(list(reversed(rows))).recommend("U", k=10)]

    assert first == again == ["p", "q"]


# --- The case the phase gate asks about -------------------------------------


def test_two_people_with_different_tastes_are_recommended_different_things():
    """Two clusters that barely touch, and one newcomer in each.

    The Python people take p1..p3, the design people take d1..d3, and one
    person crosses over once. Someone who has only p1 must be pointed at the
    rest of the Python cluster before anything from design, and the mirror
    image for d1 -- which is the gate's "2 user sở thích khác nhau thấy gợi ý
    khác nhau", in miniature.
    """
    rows = []
    for user in ("py1", "py2", "py3"):
        rows += triples((user, "p1", 2), (user, "p2", 2), (user, "p3", 3))
    for user in ("de1", "de2", "de3"):
        rows += triples((user, "d1", 2), (user, "d2", 3), (user, "d3", 2))
    rows += triples(("bridge", "p3", 1), ("bridge", "d1", 1))
    rows += triples(("new_py", "p1", 2), ("new_de", "d1", 2))

    model = fit(rows)
    python_side = [r.course_id for r in model.recommend("new_py", k=2)]
    design_side = [r.course_id for r in model.recommend("new_de", k=2)]

    assert set(python_side) == {"p2", "p3"}
    assert set(design_side) == {"d2", "d3"}


def test_the_model_can_hand_back_the_history_it_was_fitted_on(interactions):
    """The hybrid's content-based half needs the same history this model used,
    reduced the same way. Rebuilding it at the call site would be the
    "strongest signal, not the sum" rule written down in two places."""
    model = fit(interactions)

    assert model.history("A") == {"x": 3, "y": 3}


def test_the_history_handed_back_is_deduplicated_like_the_model_s_own(interactions):
    doubled = [*interactions, Interaction(user_id="A", course_id="x", weight=1)]

    assert fit(doubled).history("A") == {"x": 3, "y": 3}


def test_a_stranger_has_an_empty_history():
    assert fit([]).history("khong-ai") == {}
