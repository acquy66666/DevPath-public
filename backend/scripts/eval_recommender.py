"""Precision@k and recall@k of the recommender, on interactions it never saw.

    python -m scripts.eval_recommender
    python -m scripts.eval_recommender --folds 5 --repeats 5 --k 3 5 10

    docker compose -f infra/docker-compose.yml exec -T backend \\
        python -m scripts.eval_recommender > docs/report/assets/phase-4/recommender-eval.md

Read-only: it loads every enrolment and every course vector, and writes
nothing back. The models are the production ones, called the way the nightly
batch calls them -- `collaborative.fit`/`recommend`, `recommend_from_history`,
`hybrid.blend` with each half handing over `DEFAULT_TOP_N` candidates -- so
what is measured is what the block on the home page is built from.

**Two protocols, because the hybrid exists for two reasons.**

* *Warm* -- k-fold cross-validation over interactions, cut per learner: every
  interaction is hidden exactly once, the model is refitted on the rest, and
  the hidden courses are what a good top-k should contain. A learner is never
  left with an empty history (that is cold start, answered by popularity, and a
  different question), and a learner with one course is never tested. The
  whole thing is repeated with differently shuffled folds, and the report
  gives the mean and the range: with 190 interactions one cut of the data is
  an anecdote.
* *Cold start* -- one course at a time, every interaction with it removed:
  the day it was published. Its former takers are the test. The collaborative
  half scores zero here by construction; this is where the content-based half
  earns its place, and `hybrid-blend.txt` §4 counted it only as "how many
  learners see it", not as recall.

**Baselines**, without which a number means nothing: *popular* (courses by how
many learners took them, counted on the training part only -- the catalogue's
`students_count` includes the held-out enrolments and would leak the answer),
*random* (the exact expectation, not a draw), and *ceiling* (what a perfect
ranking would score: with one course held out and k places, 1/k).

**Keys are email and slug, not UUIDs.** UUIDs are minted per database, so a
fold cut by sorting them would differ on every machine that reran the seed.
The seed writes emails and slugs, which is what makes the published folds the
folds anyone gets.

Markdown on stdout, progress on stderr.
"""

import argparse
import asyncio
import hashlib
import random
import statistics
import sys
import time
from collections import defaultdict
from collections.abc import Collection, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.models import Course, User
from app.services.collaborative import Interaction, ItemModel, fit, load_interactions
from app.services.content_based import CourseVector, load_vectors, recommend_from_history
from app.services.hybrid import (
    DEFAULT_WEIGHTS,
    FUSION_DEPTH,
    RRF_K,
    SOURCE_COLLABORATIVE,
    SOURCE_CONTENT,
    blend,
)
from app.services.recommendations import DEFAULT_TOP_N

#: Written down rather than drawn: an evaluation is reproducible only if the
#: default reproduces it. 01/11/2026 is the day Phase 4 closes.
EVAL_SEED = 20261101
DEFAULT_FOLDS = 5
DEFAULT_REPEATS = 5
#: 3: the "tương tự" and "học tiếp theo" rows. 4: the home page's block.
#: 8: the API's default page. 5 and 10: the usual reference points.
DEFAULT_KS = (3, 4, 5, 8, 10)

#: How long a list each half is asked for. The longest any variant cuts to:
#: the batch's `top_n`, which is also what each half handed the blend before
#: `FUSION_DEPTH` existed.
DEPTH = DEFAULT_TOP_N

UserKey = Hashable
CourseKey = Hashable


# --- Cutting the data ----------------------------------------------------------


@dataclass(frozen=True)
class Fold:
    """One refit: what the models learn from, and what they are asked to find."""

    train: tuple[Interaction, ...]
    test: Mapping[UserKey, frozenset[CourseKey]]


def _by_user(interactions: Iterable[Interaction]) -> dict[UserKey, dict[CourseKey, int]]:
    """One weight per (learner, course), the strongest -- the rule `fit` uses."""
    history: dict[UserKey, dict[CourseKey, int]] = defaultdict(dict)
    for row in interactions:
        courses = history[row.user_id]
        courses[row.course_id] = max(courses.get(row.course_id, 0), row.weight)
    return history


def _canonical(history: Mapping[UserKey, Mapping[CourseKey, int]]) -> list[Interaction]:
    """Every interaction in one fixed order, whatever order the rows came in."""
    return [
        Interaction(user_id=user, course_id=course, weight=weight)
        for user in sorted(history, key=str)
        for course, weight in sorted(history[user].items(), key=lambda item: str(item[0]))
    ]


def split_folds(
    interactions: Iterable[Interaction], *, folds: int, seed: int
) -> list[Fold]:
    """k-fold cross-validation, cut per learner.

    Each learner's courses are shuffled and dealt round-robin into the folds
    from a random starting fold, so every interaction is held out exactly once
    and the folds stay the same size. A learner's courses never all land in
    one fold: with n ≥ 2 courses a fold holds at most ⌈n / folds⌉ ≤ ⌈n / 2⌉ < n
    of them. A learner with a single course is kept for training and never
    tested -- holding it out would leave nothing to recommend from.
    """
    if folds < 2:
        raise ValueError("cần ít nhất 2 fold")

    history = _by_user(interactions)
    rng = random.Random(seed)
    fold_of: dict[tuple[UserKey, CourseKey], int] = {}
    for user in sorted(history, key=str):
        courses = sorted(history[user], key=str)
        if len(courses) < 2:
            continue
        rng.shuffle(courses)
        start = rng.randrange(folds)
        for index, course in enumerate(courses):
            fold_of[(user, course)] = (start + index) % folds

    rows = _canonical(history)
    result = []
    for number in range(folds):
        test: dict[UserKey, set[CourseKey]] = defaultdict(set)
        train = []
        for row in rows:
            if fold_of.get((row.user_id, row.course_id)) == number:
                test[row.user_id].add(row.course_id)
            else:
                train.append(row)
        result.append(
            Fold(
                train=tuple(train),
                test={user: frozenset(courses) for user, courses in test.items()},
            )
        )
    return result


def cold_start_folds(interactions: Iterable[Interaction]) -> list[Fold]:
    """One fold per course, with every interaction touching it removed.

    The state a course is in the day it is published. Its former takers are
    the test -- those with something else left to be recommended from.
    """
    history = _by_user(interactions)
    rows = _canonical(history)
    courses = sorted({row.course_id for row in rows}, key=str)
    return [
        Fold(
            train=tuple(row for row in rows if row.course_id != course),
            test={
                user: frozenset({course})
                for user in sorted(history, key=str)
                if course in history[user] and len(history[user]) > 1
            },
        )
        for course in courses
    ]


# --- The measures ----------------------------------------------------------------


def _hits(ranked: Sequence[CourseKey], relevant: Collection[CourseKey], k: int) -> int:
    return sum(1 for course in ranked[:k] if course in relevant)


def precision_at_k(
    ranked: Sequence[CourseKey], relevant: Collection[CourseKey], k: int
) -> float:
    """Hits in the top k, over k -- not over how many the model named. An empty
    place in a short list is a miss, which is what the reader sees."""
    return _hits(ranked, relevant, k) / k


def recall_at_k(
    ranked: Sequence[CourseKey], relevant: Collection[CourseKey], k: int
) -> float:
    """Hits in the top k, over how many there were to find."""
    return _hits(ranked, relevant, k) / len(relevant)


def random_expectation(*, relevant: int, candidates: int, k: int) -> tuple[float, float]:
    """(precision@k, recall@k) of a uniformly random ranking, exactly.

    Of `candidates` courses the learner does not have, `relevant` are right. A
    random top-k shows min(k, candidates) of them, each right with probability
    relevant / candidates.
    """
    if candidates == 0:
        return 0.0, 0.0
    hits = min(k, candidates) * relevant / candidates
    return hits / k, hits / relevant


def popularity_ranking(interactions: Iterable[Interaction]) -> list[CourseKey]:
    """Courses by how many learners took them, most first, ties by id."""
    takers: dict[CourseKey, set[UserKey]] = defaultdict(set)
    for row in interactions:
        takers[row.course_id].add(row.user_id)
    return sorted(takers, key=lambda course: (-len(takers[course]), str(course)))


def recommend_popular(
    ranking: Sequence[CourseKey], *, owned: Collection[CourseKey], k: int
) -> list[CourseKey]:
    return [course for course in ranking if course not in owned][:k]


# --- Running the models ------------------------------------------------------------


@dataclass(frozen=True)
class HybridVariant:
    """One setting of the blend: the production one, or one to compare with."""

    name: str
    weights: Mapping[str, float]
    k: int = RRF_K
    #: How many of each half's list the blend is handed. None: the whole list
    #: the evaluation asked for, which is `DEPTH` -- what the nightly batch
    #: hands it. This turned out to be the setting that matters most: see the
    #: cold-start section of the report.
    depth: int | None = None


#: What the nightly batch runs.
PRODUCTION = HybridVariant(
    "hybrid", weights=DEFAULT_WEIGHTS, k=RRF_K, depth=FUSION_DEPTH
)

#: What it ran until 21/09/2026: each half's whole top-`top_n` list. Kept in
#: the report because it is the configuration every earlier number -- the
#: 0,8056 of `hybrid-blend.txt` §3 among them -- was measured on.
BEFORE = HybridVariant(
    "hybrid-before", weights=DEFAULT_WEIGHTS, k=RRF_K, depth=DEFAULT_TOP_N
)

#: Depth first, at the production weights and k, because it decides whether a
#: course only one half knows about can reach the top at all. Then weights and
#: k at the production depth. A map of the trade-off, not a search for the
#: winner: the data is generated from the same clusters it is scored on.
SENSITIVITY = (
    *(
        HybridVariant(
            f"độ sâu {depth}", weights=DEFAULT_WEIGHTS, k=RRF_K, depth=depth
        )
        for depth in (2, 3, 4, 5, 6, 8, 10, 15, 20)
    ),
    *(
        HybridVariant(
            f"độ sâu {FUSION_DEPTH} · CF {cf:g} : content {content:g} · k = {k}",
            weights={SOURCE_COLLABORATIVE: cf, SOURCE_CONTENT: content},
            k=k,
            depth=FUSION_DEPTH,
        )
        for cf, content, k in ((2, 1, RRF_K), (1, 2, RRF_K), (1, 1, 10))
    ),
)

#: The order rows appear in, baselines first.
MODEL_ORDER = ("ceiling", "random", "popular", "collaborative", "content")


@dataclass
class Metrics:
    """Mean precision@k and recall@k over the test cases one run scored."""

    cases: int = 0
    precision: dict[int, float] = field(default_factory=dict)
    recall: dict[int, float] = field(default_factory=dict)


def _rank(
    model: ItemModel,
    vectors: Sequence[CourseVector],
    popular: Sequence[CourseKey],
    user: UserKey,
    owned: Mapping[CourseKey, int],
    *,
    depth: int,
    limit: int,
    variants: Sequence[HybridVariant],
) -> dict[str, list[CourseKey]]:
    """Every model's top-`limit` for one learner, from one fitted fold."""
    collaborative = model.recommend(user, k=depth)
    content = recommend_from_history(vectors, owned, k=depth)
    lists = {
        "popular": recommend_popular(popular, owned=owned, k=limit),
        "collaborative": [item.course_id for item in collaborative[:limit]],
        "content": [item.course_id for item in content[:limit]],
    }
    for variant in variants:
        cut = depth if variant.depth is None else variant.depth
        fused = blend(
            {SOURCE_COLLABORATIVE: collaborative[:cut], SOURCE_CONTENT: content[:cut]},
            weights=variant.weights,
            k=variant.k,
            limit=limit,
        )
        lists[variant.name] = [item.course_id for item in fused]
    return lists


def evaluate(
    folds: Iterable[Fold],
    vectors: Sequence[CourseVector],
    catalogue: Collection[CourseKey],
    *,
    ks: Sequence[int],
    variants: Sequence[HybridVariant],
    depth: int = DEPTH,
) -> dict[str, Metrics]:
    """Fit each fold, ask every model about every test learner, average.

    A test case is one learner in one fold; every case weighs the same.
    """
    names = [*MODEL_ORDER, *(variant.name for variant in variants)]
    precision = {name: defaultdict(float) for name in names}
    recall = {name: defaultdict(float) for name in names}
    cases = 0
    limit = max(ks)

    for fold in folds:
        model = fit(fold.train)
        popular = popularity_ranking(fold.train)
        for user in sorted(fold.test, key=str):
            relevant = fold.test[user]
            owned = model.history(user)
            if not owned:
                continue
            cases += 1

            lists = _rank(
                model, vectors, popular, user, owned,
                depth=depth, limit=limit, variants=variants,
            )
            candidates = len(set(catalogue) - set(owned))
            for k in ks:
                for name, ranked in lists.items():
                    precision[name][k] += precision_at_k(ranked, relevant, k)
                    recall[name][k] += recall_at_k(ranked, relevant, k)

                chance = random_expectation(
                    relevant=len(relevant), candidates=candidates, k=k
                )
                precision["random"][k] += chance[0]
                recall["random"][k] += chance[1]

                reachable = min(k, len(relevant))
                precision["ceiling"][k] += reachable / k
                recall["ceiling"][k] += reachable / len(relevant)

    return {
        name: Metrics(
            cases=cases,
            precision={k: precision[name][k] / cases if cases else 0.0 for k in ks},
            recall={k: recall[name][k] / cases if cases else 0.0 for k in ks},
        )
        for name in names
    }


@dataclass
class Summary:
    """One model over several runs: (mean, lowest, highest) per k."""

    cases: tuple[int, ...]
    precision: dict[int, tuple[float, float, float]]
    recall: dict[int, tuple[float, float, float]]


def _spread(values: Sequence[float]) -> tuple[float, float, float]:
    return statistics.fmean(values), min(values), max(values)


def summarize(runs: Sequence[Mapping[str, Metrics]]) -> dict[str, Summary]:
    return {
        name: Summary(
            cases=tuple(sorted({run[name].cases for run in runs})),
            precision={
                k: _spread([run[name].precision[k] for run in runs])
                for k in runs[0][name].precision
            },
            recall={
                k: _spread([run[name].recall[k] for run in runs])
                for k in runs[0][name].recall
            },
        )
        for name in runs[0]
    }


# --- Reading the database -------------------------------------------------------------


@dataclass(frozen=True)
class Dataset:
    interactions: list[Interaction]
    vectors: list[CourseVector]
    #: Every course that could be recommended, by slug.
    catalogue: frozenset[str]
    embedding_model: str


async def load_dataset(session: AsyncSession, *, embedding_model: str) -> Dataset:
    """What the nightly batch reads, re-keyed by email and slug."""
    raw = await load_interactions(session)
    emails = dict(
        (
            await session.execute(
                select(User.id, User.email).where(
                    User.id.in_({row.user_id for row in raw})
                )
            )
        ).all()
    )
    slugs = dict(
        (
            await session.execute(
                select(Course.id, Course.slug).where(
                    Course.status == "published", Course.deleted_at.is_(None)
                )
            )
        ).all()
    )
    vectors = sorted(
        (
            CourseVector(course_id=slugs[vector.course_id], embedding=vector.embedding)
            for vector in await load_vectors(session, model=embedding_model)
            if vector.course_id in slugs
        ),
        key=lambda vector: vector.course_id,
    )
    return Dataset(
        interactions=[
            Interaction(
                user_id=emails[row.user_id],
                course_id=slugs[row.course_id],
                weight=row.weight,
            )
            for row in raw
        ],
        vectors=vectors,
        catalogue=frozenset(slugs.values()),
        embedding_model=embedding_model,
    )


def fingerprint(interactions: Iterable[Interaction]) -> str:
    """A short hash of the data, so a rerun can tell it measured the same thing."""
    lines = sorted(f"{r.user_id}\t{r.course_id}\t{r.weight}" for r in interactions)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:12]


# --- The report ----------------------------------------------------------------------------


LABELS = {
    "ceiling": "*Trần lý thuyết* (xếp hạng hoàn hảo)",
    "random": "Ngẫu nhiên (kỳ vọng)",
    "popular": "Phổ biến (đếm trên tập train)",
    "collaborative": "Collaborative (item-based CF)",
    "content": "Content-based",
    "hybrid": f"**Hybrid — cấu hình đang chạy** (độ sâu {FUSION_DEPTH})",
    "hybrid-before": f"Hybrid — trước 21/09 (độ sâu {DEFAULT_TOP_N})",
}


def _n(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def _cell(spread: tuple[float, float, float], repeats: int) -> str:
    mean, low, high = spread
    if repeats == 1 or low == high:
        return _n(mean)
    return f"{_n(mean)} ({_n(low)}–{_n(high)})"


def _table(
    summary: Mapping[str, Summary], names: Sequence[str], ks: Sequence[int], repeats: int
) -> list[str]:
    header = "| Mô hình | " + " | ".join(f"P@{k} | R@{k}" for k in ks) + " |"
    rule = "|---|" + "---|---|" * len(ks)
    rows = [header, rule]
    for name in names:
        score = summary[name]
        cells = " | ".join(
            f"{_cell(score.precision[k], repeats)} | {_cell(score.recall[k], repeats)}"
            for k in ks
        )
        rows.append(f"| {LABELS.get(name, name)} | {cells} |")
    return rows


def _recall_only(
    warm: Mapping[str, Summary],
    cold: Mapping[str, Summary],
    names: Sequence[str],
    ks: Sequence[int],
) -> list[str]:
    header = (
        "| Cấu hình | "
        + " | ".join(f"warm R@{k}" for k in ks)
        + " | "
        + " | ".join(f"cold R@{k}" for k in ks)
        + " |"
    )
    rows = [header, "|---|" + "---|" * (2 * len(ks))]
    for name in names:
        cells = [_n(warm[name].recall[k][0]) for k in ks] + [
            _n(cold[name].recall[k][0]) for k in ks
        ]
        rows.append(f"| {LABELS.get(name, name)} | " + " | ".join(cells) + " |")
    return rows


def report(
    dataset: Dataset,
    warm: Mapping[str, Summary],
    cold: Mapping[str, Summary],
    *,
    folds: int,
    repeats: int,
    seed: int,
    ks: Sequence[int],
    elapsed: float,
) -> str:
    learners = _by_user(dataset.interactions)
    sizes = sorted(len(courses) for courses in learners.values())
    size_counts = ", ".join(
        f"{size} khóa: {sizes.count(size)}" for size in sorted(set(sizes))
    )
    cold_runs = len(cold_start_folds(dataset.interactions))
    main = [*MODEL_ORDER, BEFORE.name, PRODUCTION.name]
    sensitivity = [variant.name for variant in SENSITIVITY]
    command = (
        "docker compose -f infra/docker-compose.yml exec -T backend "
        "python -m scripts.eval_recommender"
    )
    if (folds, repeats, seed, tuple(ks)) != (
        DEFAULT_FOLDS, DEFAULT_REPEATS, EVAL_SEED, DEFAULT_KS
    ):
        command += (
            f" --folds {folds} --repeats {repeats} --seed {seed} --k "
            + " ".join(str(k) for k in ks)
        )

    lines = [
        "# Đánh giá recommender trên tập held-out — precision@k, recall@k",
        "",
        f"- Ngày chạy: {datetime.now(UTC):%d/%m/%Y %H:%M} UTC · stack dev · "
        f"chỉ đọc CSDL, không gọi Gemini · {elapsed:.1f} s",
        f"- Dữ liệu: {len(dataset.interactions)} tương tác · {len(learners)} học viên "
        f"({size_counts}) · {len(dataset.catalogue)} khóa trong catalogue · "
        f"{len(dataset.vectors)} vector `{dataset.embedding_model}` · "
        f"dấu vân tay `{fingerprint(dataset.interactions)}`",
        f"- Warm: {folds} fold cắt theo từng học viên × {repeats} lần xáo "
        f"(hạt giống {seed}…{seed + repeats - 1}) · cold-start: {cold_runs} lần, "
        "mỗi lần một khóa",
        f"- Mỗi nửa đưa cho blend {FUSION_DEPTH} ứng viên (`FUSION_DEPTH`), như job "
        f"hằng đêm · RRF k = {RRF_K}, "
        f"trọng số collaborative {DEFAULT_WEIGHTS[SOURCE_COLLABORATIVE]:g} : "
        f"content {DEFAULT_WEIGHTS[SOURCE_CONTENT]:g}",
        "- Tái tạo (từ thư mục gốc repo, sau `scripts.seed`, `scripts.seed_interactions`, "
        "`scripts.rebuild_course_embeddings`):",
        f"  `{command} > docs/report/assets/phase-4/recommender-eval.md`",
        "",
        "**Dữ liệu là giả lập** (`scripts/seed_interactions.py`: 4 cụm sở thích, "
        "hạt giống cố định). Con số đo được là khả năng khôi phục một cấu trúc đã "
        "biết là có, không phải bằng chứng người học thật thấy gợi ý hữu ích.",
        "",
        "Precision@k chia cho k kể cả khi mô hình trả ít hơn k khóa — chỗ trống là "
        "chỗ trượt. Recall@k chia cho số khóa bị giấu. Mỗi ca kiểm là một học viên "
        "trong một fold; mọi ca nặng như nhau. Ô có ngoặc: trung bình (thấp nhất–"
        "cao nhất) qua các lần xáo.",
        "",
        "## 1. Warm — giấu tương tác của người đã có lịch sử",
        "",
        f"Mỗi tương tác bị giấu đúng một lần; mô hình khớp lại trên phần còn lại. "
        f"Số ca kiểm mỗi lần xáo: {', '.join(str(c) for c in warm['hybrid'].cases)}.",
        "",
        *_table(warm, main, ks, repeats),
        "",
        "## 2. Cold-start — ngày một khóa vừa xuất bản",
        "",
        "Với từng khóa: gỡ mọi tương tác chạm tới nó, khớp lại, rồi hỏi những người "
        "từng học nó xem khóa ấy có lọt top-k không. Collaborative bằng 0 theo cấu "
        "tạo — khóa chưa ai học không đồng xuất hiện với gì cả. "
        f"Số ca kiểm: {', '.join(str(c) for c in cold['hybrid'].cases)}.",
        "",
        *_table(cold, main, ks, 1),
        "",
        "## 3. Độ nhạy: độ sâu, trọng số, hằng số k",
        "",
        "Độ sâu = số ứng viên mỗi nửa đưa cho blend (job hằng đêm dùng "
        f"{FUSION_DEPTH}, trước 21/09 là {DEFAULT_TOP_N}). Các hàng độ sâu dùng "
        f"trọng số 1 : 1 và k = {RRF_K}. Chỉ recall; ở cả hai giao thức gần như "
        "mọi ca giấu đúng một khóa nên precision@k ≈ recall@k / k. Warm là trung "
        "bình qua các lần xáo. Đây là bản đồ đánh đổi, không phải cuộc tìm cấu "
        "hình thắng: dữ liệu được sinh từ chính các cụm mà nó được chấm theo.",
        "",
        *_recall_only(warm, cold, sensitivity, ks),
        "",
    ]
    return "\n".join(lines)


# --- Entry point -----------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folds", type=int, default=DEFAULT_FOLDS)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--seed", type=int, default=EVAL_SEED)
    parser.add_argument("--k", type=int, nargs="+", default=list(DEFAULT_KS))
    args = parser.parse_args()

    started = time.perf_counter()
    # The report goes to stdout, and the dev engine echoes every query there.
    engine.echo = False
    model_name = get_settings().gemini_embedding_model
    async with SessionLocal() as session:
        dataset = await load_dataset(session, embedding_model=model_name)
    await engine.dispose()

    if not dataset.interactions:
        sys.exit("Không có tương tác nào — chạy scripts.seed_interactions trước.")
    if not dataset.vectors:
        print(
            f"Cảnh báo: không có vector nào cho {model_name} — nửa content-based "
            "sẽ rỗng. Chạy scripts.rebuild_course_embeddings trước.",
            file=sys.stderr,
        )

    variants = (PRODUCTION, BEFORE, *SENSITIVITY)
    runs = []
    for repeat in range(args.repeats):
        print(f"warm: lần xáo {repeat + 1}/{args.repeats}", file=sys.stderr)
        runs.append(
            evaluate(
                split_folds(dataset.interactions, folds=args.folds, seed=args.seed + repeat),
                dataset.vectors,
                dataset.catalogue,
                ks=args.k,
                variants=variants,
            )
        )
    print("cold-start", file=sys.stderr)
    cold = evaluate(
        cold_start_folds(dataset.interactions),
        dataset.vectors,
        dataset.catalogue,
        ks=args.k,
        variants=variants,
    )

    print(
        report(
            dataset,
            summarize(runs),
            summarize([cold]),
            folds=args.folds,
            repeats=args.repeats,
            seed=args.seed,
            ks=args.k,
            elapsed=time.perf_counter() - started,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
