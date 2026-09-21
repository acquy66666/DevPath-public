"""`scripts/eval_recommender.py`, checked on data small enough to do by hand.

The numbers the script prints go into the thesis, so every piece that turns
interactions into a number is pinned here first: how the folds are cut (every
interaction held out exactly once, nobody's history emptied, the same folds on
every machine), what precision@k and recall@k mean for a short list, that the
popularity baseline learns only from the training part, and that on two
disjoint clusters each model scores what it can be worked out to score.
"""

import random
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, CourseEmbedding, Enrollment, User
from app.services.collaborative import Interaction
from app.services.content_based import CourseVector
from app.services.hybrid import SOURCE_COLLABORATIVE, SOURCE_CONTENT
from scripts.eval_recommender import (
    Fold,
    HybridVariant,
    cold_start_folds,
    evaluate,
    load_dataset,
    popularity_ranking,
    precision_at_k,
    random_expectation,
    recall_at_k,
    recommend_popular,
    split_folds,
    summarize,
)
from tests.test_content_based import axis

HYBRID = HybridVariant(
    "hybrid", weights={SOURCE_COLLABORATIVE: 1.0, SOURCE_CONTENT: 1.0}
)


def taken(user: str, *courses: str, weight: int = 1) -> list[Interaction]:
    return [Interaction(user_id=user, course_id=c, weight=weight) for c in courses]


def many_learners() -> list[Interaction]:
    """Twenty learners with two to five courses each, from a fixed seed."""
    rng = random.Random(7)
    catalogue = [f"c{n:02d}" for n in range(12)]
    rows: list[Interaction] = []
    for n in range(20):
        rows += taken(f"u{n:02d}", *rng.sample(catalogue, rng.randint(2, 5)))
    return rows


# --- Cutting the folds --------------------------------------------------------


def test_every_interaction_is_held_out_exactly_once():
    rows = many_learners()

    folds = split_folds(rows, folds=5, seed=1)

    held_out = [
        (user, course) for fold in folds for user, courses in fold.test.items()
        for course in courses
    ]
    assert sorted(held_out) == sorted((r.user_id, r.course_id) for r in rows)


def test_each_fold_trains_on_everything_it_does_not_test():
    rows = many_learners()

    for fold in split_folds(rows, folds=5, seed=1):
        tested = {(u, c) for u, courses in fold.test.items() for c in courses}
        trained = {(r.user_id, r.course_id) for r in fold.train}
        assert tested.isdisjoint(trained)
        assert tested | trained == {(r.user_id, r.course_id) for r in rows}


def test_nobody_has_their_whole_history_held_out():
    """A learner with nothing left to train on is a cold-start user, which is
    a different question -- and the recommender answers it with popularity."""
    rows = taken("two", "a", "b") + taken("five", "a", "b", "c", "d", "e")

    for fold in split_folds(rows, folds=2, seed=3):
        for user, courses in fold.test.items():
            left = {r.course_id for r in fold.train if r.user_id == user}
            assert left, f"{user} has no training history in this fold"
            assert courses


def test_a_learner_with_one_course_is_never_tested():
    rows = taken("alone", "a") + taken("pair", "a", "b")

    folds = split_folds(rows, folds=2, seed=1)

    assert all("alone" not in fold.test for fold in folds)
    assert all(
        Interaction(user_id="alone", course_id="a", weight=1) in fold.train
        for fold in folds
    )


def test_the_folds_do_not_depend_on_the_order_rows_arrived_in():
    """The database returns rows in whatever order it likes; a fold that moved
    with it would make the published numbers unrepeatable."""
    rows = many_learners()
    shuffled = rows[:]
    random.Random(99).shuffle(shuffled)

    assert split_folds(rows, folds=5, seed=1) == split_folds(shuffled, folds=5, seed=1)


def test_another_seed_cuts_other_folds():
    rows = many_learners()

    assert split_folds(rows, folds=5, seed=1) != split_folds(rows, folds=5, seed=2)


# --- The measures ------------------------------------------------------------


def test_precision_and_recall_at_k_by_hand():
    ranked = ["a", "b", "c", "d"]
    relevant = {"b", "d", "x"}

    assert precision_at_k(ranked, relevant, 2) == pytest.approx(1 / 2)
    assert recall_at_k(ranked, relevant, 2) == pytest.approx(1 / 3)
    assert precision_at_k(ranked, relevant, 4) == pytest.approx(2 / 4)
    assert recall_at_k(ranked, relevant, 4) == pytest.approx(2 / 3)


def test_a_short_list_is_not_let_off_its_empty_places():
    """Precision divides by k, not by how many the model managed to name: a
    model that returns one course when asked for three has left two places
    empty, and those count as misses."""
    assert precision_at_k(["a"], {"a"}, 3) == pytest.approx(1 / 3)
    assert recall_at_k(["a"], {"a"}, 3) == 1.0


def test_random_is_an_expectation_not_a_draw():
    """One relevant course among 20 candidates, 5 places: 5 × 1/20 = 0,25
    expected hits."""
    precision, recall = random_expectation(relevant=1, candidates=20, k=5)

    assert precision == pytest.approx(0.25 / 5)
    assert recall == pytest.approx(0.25)


def test_random_with_fewer_candidates_than_places_finds_everything():
    precision, recall = random_expectation(relevant=1, candidates=3, k=5)

    assert recall == 1.0
    assert precision == pytest.approx(1 / 5)


# --- The popularity baseline -------------------------------------------------


def test_popularity_counts_learners_and_breaks_ties_by_id():
    rows = (
        taken("u1", "x", "z") + taken("u2", "x", "y") + taken("u3", "x", "y", "z")
    )

    assert popularity_ranking(rows) == ["x", "y", "z"]


def test_popularity_learns_only_from_what_it_is_given():
    """Computed from the training part of a fold, never from the catalogue's
    `students_count` -- which counts the held-out enrolments too, and would
    quietly tell the baseline the answer."""
    rows = taken("u1", "a", "b") + taken("u2", "a", "b") + taken("u3", "b", "c")
    fold = Fold(
        train=tuple(r for r in rows if r.course_id != "a"),
        test={"u1": frozenset({"a"}), "u2": frozenset({"a"})},
    )

    assert popularity_ranking(fold.train) == ["b", "c"]


def test_the_popular_list_leaves_out_what_the_learner_has():
    assert recommend_popular(["x", "y", "z"], owned={"x"}, k=5) == ["y", "z"]


# --- Evaluating on data whose answer is known ---------------------------------


def two_clusters() -> list[Interaction]:
    """Three learners took a1–a3 and three others took b1–b3. Nothing crosses."""
    rows: list[Interaction] = []
    for user in ("u1", "u2", "u3"):
        rows += taken(user, "a1", "a2", "a3")
    for user in ("v1", "v2", "v3"):
        rows += taken(user, "b1", "b2", "b3")
    return rows


def cluster_vectors() -> list[CourseVector]:
    """a-courses on one axis, b-courses on another: cosine 1 within, 0 across."""
    return [CourseVector(course_id=f"a{n}", embedding=axis(0)) for n in (1, 2, 3)] + [
        CourseVector(course_id=f"b{n}", embedding=axis(1)) for n in (1, 2, 3)
    ]


CATALOGUE = {"a1", "a2", "a3", "b1", "b2", "b3"}


def hold_out_a3_from_u1() -> Fold:
    rows = two_clusters()
    return Fold(
        train=tuple(r for r in rows if (r.user_id, r.course_id) != ("u1", "a3")),
        test={"u1": frozenset({"a3"})},
    )


def test_each_model_scores_what_it_can_be_worked_out_to_score():
    """u1 keeps a1 and a2; a3 is hidden.

    * collaborative: a3 is the only course taken alongside a1/a2 → found at 1.
    * content: a3 sits on a1/a2's axis → found at 1.
    * popular: b1–b3 have three learners each, a3 now has two → a3 is 4th.
    * random: 4 candidates, 1 relevant → 1/4 at k=1.
    """
    scores = evaluate(
        [hold_out_a3_from_u1()],
        cluster_vectors(),
        CATALOGUE,
        ks=(1, 4),
        variants=(HYBRID,),
        depth=20,
    )

    for model in ("collaborative", "content", "hybrid"):
        assert scores[model].precision[1] == 1.0, model
        assert scores[model].recall[1] == 1.0, model
    assert scores["popular"].recall[1] == 0.0
    assert scores["popular"].recall[4] == 1.0
    assert scores["random"].recall[1] == pytest.approx(1 / 4)
    assert scores["random"].precision[4] == pytest.approx(1 / 4)
    assert all(score.cases == 1 for score in scores.values())


def test_the_ceiling_is_what_a_perfect_ranking_would_score():
    """With one course held out, even a perfect model scores 1/k on precision:
    there is one right answer and k places. Without this row a precision@10
    of 0,08 reads as a failure when the best possible is 0,10."""
    scores = evaluate(
        [hold_out_a3_from_u1()],
        cluster_vectors(),
        CATALOGUE,
        ks=(1, 4),
        variants=(),
        depth=20,
    )

    assert scores["ceiling"].precision[1] == 1.0
    assert scores["ceiling"].precision[4] == pytest.approx(1 / 4)
    assert scores["ceiling"].recall[4] == 1.0


def test_scores_are_the_mean_over_test_cases():
    """Two cases: one hit and one miss at k=1 average to one half."""
    rows = two_clusters() + taken("w", "a1", "b1")
    fold = Fold(
        train=tuple(r for r in rows if (r.user_id, r.course_id) != ("w", "b1")),
        # w keeps a1; b1 is hidden. u1 keeps a1, a2; a3 is hidden.
        test={"w": frozenset({"b1"})},
    )
    scores = evaluate(
        [hold_out_a3_from_u1(), fold],
        cluster_vectors(),
        CATALOGUE,
        ks=(1,),
        variants=(),
        depth=20,
    )

    # For w, collaborative sees a1 taken alongside a2/a3 and ranks one of them
    # first -- b1 is not at 1. For u1 it finds a3. One of two.
    assert scores["collaborative"].cases == 2
    assert scores["collaborative"].recall[1] == pytest.approx(1 / 2)


def test_a_course_nobody_has_taken_is_invisible_to_collaborative_only():
    """The cold-start protocol: every interaction with a3 is removed. The
    collaborative half cannot name a course it has never seen; the content
    half can, because a newly published course has a vector the day it goes
    live."""
    folds = cold_start_folds(two_clusters())
    a3 = next(fold for fold in folds if "a3" in next(iter(fold.test.values())))

    scores = evaluate(
        [a3], cluster_vectors(), CATALOGUE, ks=(1,), variants=(HYBRID,), depth=20
    )

    assert scores["collaborative"].recall[1] == 0.0
    assert scores["content"].recall[1] == 1.0
    assert scores["hybrid"].recall[1] == 1.0
    assert scores["content"].cases == 3


def test_a_variant_cuts_each_list_to_its_depth_before_fusing():
    """The mechanism the evaluation found, small enough to do by hand.

    a3 has just been published. u1 has a1 and a2; learner x took a1, a2 and
    b1, so collaborative offers u1 [b1]. Every course is somewhat alike (b
    sits 45° from a), so content offers [a3, b1, b2, b3] -- a3 first, and b1
    *also* in the list.

    * At depth 20 b1 is in both lists: 1/61 + 1/62 beats a3's lone 1/61, and
      the new course is pushed off the top place.
    * At depth 1 content hands over only [a3]: a3 and b1 tie at 1/61 and a3
      wins on id -- the new course is shown.
    """
    rows = two_clusters() + taken("x", "a1", "a2", "b1")
    vectors = [CourseVector(course_id=f"a{n}", embedding=axis(0)) for n in (1, 2, 3)] + [
        CourseVector(course_id=f"b{n}", embedding=axis(0, 1)) for n in (1, 2, 3)
    ]
    fold = next(f for f in cold_start_folds(rows) if "a3" in f.test.get("u1", ()))
    fold = Fold(train=fold.train, test={"u1": fold.test["u1"]})
    wide = HybridVariant("wide", weights=HYBRID.weights, depth=20)
    narrow = HybridVariant("narrow", weights=HYBRID.weights, depth=1)

    scores = evaluate(
        [fold], vectors, CATALOGUE, ks=(1,), variants=(wide, narrow), depth=20
    )

    assert scores["content"].recall[1] == 1.0
    assert scores["wide"].recall[1] == 0.0
    assert scores["narrow"].recall[1] == 1.0


def test_cold_start_holds_out_one_course_from_everybody_who_took_it():
    rows = two_clusters() + taken("only-a3", "a3")

    folds = cold_start_folds(rows)

    a3 = next(fold for fold in folds if "u1" in fold.test and "a3" in fold.test["u1"])
    assert all(r.course_id != "a3" for r in a3.train)
    # Somebody whose only course was a3 has nothing to be recommended from.
    assert set(a3.test) == {"u1", "u2", "u3"}
    assert len(folds) == 6


def test_summarize_reports_the_mean_and_the_range_over_repeats():
    runs = []
    for value in (0.2, 0.4, 0.3):
        scores = evaluate(
            [hold_out_a3_from_u1()],
            cluster_vectors(),
            CATALOGUE,
            ks=(1,),
            variants=(),
            depth=20,
        )
        scores["collaborative"].recall[1] = value
        runs.append(scores)

    summary = summarize(runs)

    mean, low, high = summary["collaborative"].recall[1]
    assert mean == pytest.approx(0.3)
    assert (low, high) == (0.2, 0.4)


# --- Reading the database ----------------------------------------------------


async def test_the_dataset_is_keyed_by_email_and_slug(db_session: AsyncSession):
    """UUIDs are minted per database, so folds cut by sorting them would differ
    on every machine that reran the seed. Email and slug are what the seed
    writes, and so what makes the published folds reproducible."""
    category = Category(name="Lập trình", slug=f"lt-{uuid.uuid4().hex[:8]}")
    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash=hash_password("mật-khẩu-đủ-dài"),
        role="instructor",
    )
    learner = User(
        email=f"hv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Học viên",
        password_hash=hash_password("mật-khẩu-đủ-dài"),
        role="student",
    )
    db_session.add_all([category, instructor, learner])
    await db_session.flush()
    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title="Khóa đo",
        slug=f"khoa-do-{uuid.uuid4().hex[:8]}",
        status="published",
        published_at=datetime.now(UTC),
    )
    db_session.add(course)
    await db_session.flush()
    db_session.add_all(
        [
            Enrollment(user_id=learner.id, course_id=course.id),
            CourseEmbedding(
                course_id=course.id,
                embedding=axis(3),
                embedding_model="eval-model",
                source_text="Khóa đo",
            ),
        ]
    )
    await db_session.flush()

    dataset = await load_dataset(db_session, embedding_model="eval-model")

    assert Interaction(user_id=learner.email, course_id=course.slug, weight=1) in (
        dataset.interactions
    )
    assert [v.course_id for v in dataset.vectors] == [course.slug]
    assert course.slug in dataset.catalogue
