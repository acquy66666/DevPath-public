"""The synthetic interaction data the recommender is measured on.

A precision@k is worth nothing if the data underneath it is an accident, so
this file pins down the properties the Phase 4 gate rests on:

* the same data comes out every time, on every machine -- an evaluation number
  nobody can reproduce is an anecdote;
* the learners really do fall into interest clusters, and each one leaves part
  of their own cluster untouched, or there would be nothing correct left to
  recommend to them;
* the model built from this data recommends inside a learner's cluster, which
  is the gate's "hai user sở thích khác nhau thấy gợi ý khác nhau" stated as an
  assertion instead of a screenshot.

The last one is the point of the whole file. It runs the real `fit` from
`app/services/collaborative.py` over the real weights, so a generator that
produced plausible-looking rows with no structure in them would fail here
rather than three tasks later, as a disappointing evaluation table.

Almost none of it needs a database. The two at the bottom do: they are what
proves the rows survive the schema and come back out of `load_interactions`
carrying the weights they went in with.
"""

from collections import Counter
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, Enrollment, User
from app.schemas.auth import LoginIn
from app.services.collaborative import (
    WEIGHT_COMPLETED,
    WEIGHT_ENROLLED,
    WEIGHT_RATED_HIGH,
    fit,
    load_interactions,
)
from scripts.seed import CATEGORY_TREE, seed_categories
from scripts.seed_courses import seed_courses
from scripts.seed_interactions import (
    CLUSTERS,
    LEARNER_COUNT,
    SYNTHETIC_COURSES,
    build_population,
    cluster_of,
    seed_interactions,
    to_interactions,
)

#: What the plan asks for: "script tạo ~50 user".
MINIMUM_LEARNERS = 45
MAXIMUM_LEARNERS = 55

#: How many recommendations a "Gợi ý cho bạn" block shows above the fold, and
#: therefore the k the cluster property is asserted at.
K = 3


def category_slugs() -> set[str]:
    slugs = set()
    for _, slug, children in CATEGORY_TREE:
        slugs.add(slug)
        slugs.update(child_slug for _, child_slug in children)
    return slugs


def population():
    return build_population()


# --- The catalogue the clusters are made of --------------------------------


def test_every_cluster_has_enough_courses_to_leave_some_unseen() -> None:
    """A learner takes some of their cluster and is recommended the rest. If a
    cluster were as small as a learner's history, there would be nothing left
    in it to recommend and the model would look wrong when the data was."""
    for cluster in CLUSTERS:
        assert len(cluster.course_slugs) >= 6, cluster.key


def test_every_course_belongs_to_exactly_one_cluster() -> None:
    seen: Counter[str] = Counter()
    for cluster in CLUSTERS:
        seen.update(cluster.course_slugs)

    duplicated = [slug for slug, count in seen.items() if count > 1]
    assert not duplicated, duplicated

    # Every synthetic course is in a cluster; the rest of the slugs are the
    # real seeded courses that anchor each cluster to the demo catalogue.
    for course in SYNTHETIC_COURSES:
        assert course.slug in seen, course.slug


def test_a_synthetic_course_fits_the_columns_it_is_written_into() -> None:
    for course in SYNTHETIC_COURSES:
        assert len(course.title) <= 200, course.slug
        assert len(course.slug) <= 220, course.slug
        assert len(course.subtitle) <= 300, course.slug
        assert course.description.strip(), course.slug


def test_every_synthetic_course_is_filed_under_a_category_that_exists() -> None:
    """The two lists live in different files and drift apart silently."""
    known = category_slugs()
    for course in SYNTHETIC_COURSES:
        assert course.category_slug in known, course.slug


def test_no_synthetic_course_collides_with_a_real_one() -> None:
    from scripts.seed_courses import COURSES

    real = {course.slug for course in COURSES}
    for course in SYNTHETIC_COURSES:
        assert course.slug not in real, course.slug


# --- The learners ----------------------------------------------------------


def test_the_population_is_the_size_the_plan_asks_for() -> None:
    learners = population()

    assert MINIMUM_LEARNERS <= LEARNER_COUNT <= MAXIMUM_LEARNERS
    assert len(learners) == LEARNER_COUNT
    assert len({learner.email for learner in learners}) == LEARNER_COUNT


def test_the_clusters_are_evenly_represented() -> None:
    """Nothing breaks if they are not, but an evaluation split across clusters
    of wildly different sizes measures the biggest one and calls it the mean."""
    counts = Counter(learner.cluster_key for learner in population())

    assert set(counts) == {cluster.key for cluster in CLUSTERS}
    assert max(counts.values()) - min(counts.values()) <= 1


def test_generating_twice_gives_exactly_the_same_data() -> None:
    """The reproducibility the thesis claims, as an assertion. Without it every
    number in the evaluation chapter is true only of one afternoon."""
    assert build_population() == build_population()


def test_a_different_seed_gives_different_data() -> None:
    """Otherwise the test above would pass on a generator that ignores its
    seed and returns a constant."""
    assert build_population(seed=1) != build_population(seed=2)


def test_every_learner_has_a_history_long_enough_to_hold_one_out() -> None:
    """`eval_recommender.py` hides one course per learner and asks the model to
    find it. That needs at least two left over to predict from."""
    for learner in population():
        assert len(learner.items) >= 3, learner.email
        slugs = [item.course_slug for item in learner.items]
        assert len(set(slugs)) == len(slugs), learner.email


def test_a_learner_leaves_at_least_two_courses_of_their_own_cluster_untouched(
) -> None:
    by_key = {cluster.key: cluster for cluster in CLUSTERS}

    for learner in population():
        cluster = by_key[learner.cluster_key]
        taken = {item.course_slug for item in learner.items}
        unseen = set(cluster.course_slugs) - taken
        assert len(unseen) >= 2, learner.email


def test_most_of_what_a_learner_takes_is_from_their_own_cluster() -> None:
    """With no noise at all the clusters would be disjoint islands and the
    model would have nothing to get wrong; with too much there would be no
    clusters left to find."""
    learners = population()
    off_cluster = 0
    total = 0

    for learner in learners:
        own = sum(
            cluster_of(item.course_slug) == learner.cluster_key
            for item in learner.items
        )
        assert own > len(learner.items) / 2, learner.email
        off_cluster += len(learner.items) - own
        total += len(learner.items)

    assert 0.05 <= off_cluster / total <= 0.30


def test_all_three_interaction_weights_are_exercised() -> None:
    """The plan's scale is enroll=1, completed=2, rated high=3. Data that only
    ever produces one of them would measure a model the platform is not
    running."""
    weights = Counter(
        interaction.weight for interaction in to_interactions(population())
    )

    assert set(weights) == {WEIGHT_ENROLLED, WEIGHT_COMPLETED, WEIGHT_RATED_HIGH}
    total = sum(weights.values())
    for weight, count in weights.items():
        assert count / total >= 0.10, (weight, count)


def test_every_course_is_taken_by_somebody() -> None:
    """A course nobody has taken can never be recommended, and every one of
    them drags precision@k down for a reason that has nothing to do with the
    model."""
    taken = {item.course_slug for learner in population() for item in learner.items}

    for cluster in CLUSTERS:
        for slug in cluster.course_slugs:
            assert slug in taken, slug


def test_every_generated_account_can_be_typed_into_the_login_form() -> None:
    """The seed writes users straight into the table, so nothing on the way in
    checks the address against the rule `/auth/login` applies on the way back.
    The real seed shipped three accounts that answered 422 for exactly this
    reason; this is that lesson, kept."""
    for learner in population():
        LoginIn(email=learner.email, password="whatever-the-password-is")


# --- What the model makes of it --------------------------------------------


def test_the_model_recommends_inside_a_learner_s_own_cluster() -> None:
    """The property the whole task exists for.

    Run over the real `fit`, with the real weights. `mean` rather than "every
    learner": a handful of learners whose off-cluster course is popular will
    legitimately be pulled towards it, and a threshold that forbids that would
    be asserting the data has no noise in it -- which the test above requires
    it to have.
    """
    learners = population()
    model = fit(to_interactions(learners))

    shares = []
    for learner in learners:
        top = model.recommend(learner.email, K)
        assert top, learner.email
        shares.append(
            sum(cluster_of(item.course_id) == learner.cluster_key for item in top)
            / len(top)
        )

    assert mean(shares) >= 0.80, mean(shares)


def test_every_recommendation_names_a_course_the_learner_has() -> None:
    """`because` is drawn on the card as "vì bạn đã học ...". A reason that is
    not in the learner's own history would be a lie on screen."""
    learners = population()
    model = fit(to_interactions(learners))

    for learner in learners:
        taken = {item.course_slug for item in learner.items}
        for item in model.recommend(learner.email, K):
            assert item.because in taken, learner.email
            assert item.course_id not in taken, learner.email


def test_two_learners_from_different_clusters_see_different_recommendations(
) -> None:
    """The gate, stated as an assertion: it is what the screenshot of the
    "Gợi ý cho bạn" block for two accounts has to show."""
    learners = population()
    model = fit(to_interactions(learners))

    first_of = {}
    for learner in learners:
        first_of.setdefault(learner.cluster_key, learner)

    keys = sorted(first_of)
    for index, key in enumerate(keys):
        for other in keys[index + 1 :]:
            mine = {r.course_id for r in model.recommend(first_of[key].email, K)}
            theirs = {r.course_id for r in model.recommend(first_of[other].email, K)}
            assert mine != theirs, (key, other)


# --- The two that need a database ------------------------------------------


async def test_the_seed_writes_rows_the_recommender_then_loads(
    db_session: AsyncSession,
) -> None:
    """End to end inside one rolled-back transaction: generate, write, and read
    it back through the loader the nightly batch uses.

    What this catches that the pure tests cannot: a weight that survives
    generation but not the schema -- a `completed_at` never written, a rating
    stored against the wrong enrolment, a course left in `draft` and therefore
    invisible to `load_interactions`.

    Asserted on the state afterwards, never on how many rows this call created:
    the counters are zero on a machine where the script has already been run,
    which is every developer's machine from the moment they run it once.
    """
    await seed_categories(db_session)
    await seed_courses(db_session)
    await seed_interactions(db_session, build_population())
    await db_session.flush()

    present = set(
        await db_session.scalars(
            select(Course.slug).where(
                Course.slug.in_([course.slug for course in SYNTHETIC_COURSES])
            )
        )
    )
    assert present == {course.slug for course in SYNTHETIC_COURSES}

    learners = {learner.email: learner for learner in build_population()}
    emails = await db_session.execute(
        select(User.id, User.email).where(User.email.in_(learners))
    )
    by_id = {user_id: email for user_id, email in emails}
    assert len(by_id) == LEARNER_COUNT

    loaded = [
        interaction
        for interaction in await load_interactions(db_session)
        if interaction.user_id in by_id
    ]

    expected = {
        (interaction.user_id, interaction.course_id): interaction.weight
        for interaction in to_interactions(list(learners.values()))
    }
    slugs = await db_session.execute(select(Course.id, Course.slug))
    slug_of = {course_id: slug for course_id, slug in slugs}

    actual = {
        (by_id[interaction.user_id], slug_of[interaction.course_id]): interaction.weight
        for interaction in loaded
    }

    assert actual == expected


async def test_running_the_seed_twice_writes_nothing_the_second_time(
    db_session: AsyncSession,
) -> None:
    """It runs after `scripts.seed` on machines that have already been seeded,
    and in CI twice in a row. A second run that doubled the enrolments would
    double every weight in the matrix."""
    await seed_categories(db_session)
    await seed_courses(db_session)
    await seed_interactions(db_session, build_population())
    await db_session.flush()

    before = await db_session.scalar(select(func.count()).select_from(Enrollment))

    again = await seed_interactions(db_session, build_population())
    await db_session.flush()

    assert (again.learners, again.courses, again.enrollments, again.reviews) == (
        0,
        0,
        0,
        0,
    )
    assert await db_session.scalar(select(func.count()).select_from(Enrollment)) == before
