"""Synthetic learners and their history, so the recommender can be measured.

    python -m scripts.seed_interactions
    python -m scripts.seed_interactions --purge

The real seed (`scripts.seed`) writes four courses. Four courses cannot show
whether a recommender works: with that many, "khóa học tương tự" is almost the
whole catalogue, and a precision@k computed over it says more about the
catalogue's size than about the model. On the development database as it stood
on 18/09/2026 the model had **five interactions across four users**, one single
pair of courses anybody had taken together, and so three of those four users
got no recommendation at all -- correct behaviour, and nothing to measure.

So this script writes two things:

* **a catalogue with shape** -- twenty courses in four interest clusters
  (frontend, backend, Python/data, computer science), each cluster anchored by
  one of the four real seeded courses so the synthetic part and the demo part
  are one catalogue rather than two;
* **forty-eight learners** whose enrolments concentrate in one cluster, with a
  minority that wander outside it, some completions and some ratings -- the
  three levels of the plan's implicit scale (enroll=1, completed=2, rated
  high=3).

**This data is fabricated and the thesis has to say so.** It measures whether
the pipeline recovers a structure that is known to be there, which is the only
thing it can honestly measure: nobody on this platform has enrolled in anything
yet. What it is not is evidence that real students would find the
recommendations useful. `docs/report/assets/phase-4/` carries that caveat next
to the numbers.

**Deterministic.** One fixed seed, `random.Random`, no dependence on dict order
or on the wall clock. Running it on another machine produces the same learners
with the same histories, which is what makes an evaluation number in the report
something a reader could reproduce rather than take on trust.

**Idempotent**, by course slug and by learner email, like the rest of the seed:
a second run writes nothing. `--purge` removes every row it created, because
twenty synthetic courses are good for measuring and bad for a live demo, and
the way out has to exist before anybody needs it in a hurry.
"""

import argparse
import asyncio
import os
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import (
    Category,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Review,
    User,
)
from app.services.collaborative import Interaction, interaction_weight

# Fixed, and written down rather than passed in: an evaluation is reproducible
# only if the default reproduces it. 20261019 is the day Phase 4 opens.
DEFAULT_SEED = 20261019

#: "~50 user" in the plan. Divisible by the four clusters, and at least as many
#: per cluster as there are courses in one -- which is what lets every course
#: be guaranteed a taker below.
LEARNER_COUNT = 48

#: Its own subdomain of the reserved example domain, so these accounts are
#: distinguishable at a glance from the real seeded ones at `devpath.example`
#: and `--purge` can find them without a list. RFC 2606 keeps both unroutable.
LEARNER_DOMAIN = "seed.devpath.example"
DEFAULT_LEARNER_PASSWORD = "devpath-learner"

# How much history one learner has. The upper bound is two below the size of a
# cluster on purpose: a learner who had taken their whole cluster would have
# nothing correct left to be recommended, and would count against precision@k
# for a reason that is an artefact of the data.
IN_CLUSTER_MIN = 3
IN_CLUSTER_MAX = 4

#: Chance a learner also took something outside their cluster. Without any of
#: this the clusters are disjoint islands and every model scores perfectly;
#: with too much there is no structure left to find.
NOISE_PROBABILITY = 0.40

COMPLETION_PROBABILITY = 0.45
RATING_PROBABILITY = 0.55
NOISE_COMPLETION_PROBABILITY = 0.10
NOISE_RATING_PROBABILITY = 0.50

#: Ratings a learner gives inside their own interests, and outside them. The
#: low end matters: `interaction_weight` lets a poor rating cancel what a
#: completion would otherwise say, and data that never exercises that branch
#: would not notice if it broke.
LIKED_RATINGS = (4, 5)
DISLIKED_RATINGS = (1, 2, 3)

SURNAMES = (
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng",
    "Huỳnh", "Phan", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô",
)
GIVEN_NAMES = (
    "An", "Bình", "Chi", "Dũng", "Giang", "Hà", "Hải", "Hương", "Khánh", "Linh",
    "Minh", "Nam", "Ngọc", "Phong", "Quân", "Thảo", "Trang", "Tuấn", "Vy", "Yến",
)


@dataclass(frozen=True, slots=True)
class SyntheticCourseSpec:
    """A catalogue entry written for measurement, not for teaching.

    It carries one article lesson -- an outline of what the course would
    cover -- so that a recommendation leading to it opens a page with something
    on it. It deliberately carries no video and no exercises: those belong to
    the four real seeded courses, which is where the demo goes.
    """

    slug: str
    title: str
    subtitle: str
    description: str
    category_slug: str
    instructor_email: str
    level: str
    price: Decimal


@dataclass(frozen=True, slots=True)
class ClusterSpec:
    """One interest, and every course that belongs to it.

    `course_slugs` mixes the synthetic courses with the real seeded course that
    anchors the cluster, so a synthetic learner's history reaches into the
    catalogue a human will actually be shown.
    """

    key: str
    name: str
    course_slugs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ItemPlan:
    course_slug: str
    completed: bool
    rating: int | None


@dataclass(frozen=True, slots=True)
class LearnerPlan:
    email: str
    full_name: str
    cluster_key: str
    items: tuple[ItemPlan, ...]


@dataclass(frozen=True, slots=True)
class Written:
    courses: int
    learners: int
    enrollments: int
    reviews: int


KHOA = "khoa.tran@devpath.example"
MAI_ANH = "mai.anh@devpath.example"


SYNTHETIC_COURSES = [
    # --- Frontend ----------------------------------------------------------
    SyntheticCourseSpec(
        slug="react-tu-so-0-component-state-va-router",
        title="React từ số 0: component, state và router",
        subtitle="Dựng giao diện bằng component, quản lý state và điều hướng nhiều trang",
        description=(
            "Khóa học đi từ một component tĩnh đến một ứng dụng nhiều trang có "
            "state dùng chung. Trọng tâm là hiểu vì sao React vẽ lại giao diện "
            "khi nào, để không phải đoán mỗi lần thấy màn hình nhấp nháy."
        ),
        category_slug="frontend",
        instructor_email=MAI_ANH,
        level="beginner",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="tailwind-css-trong-du-an-that",
        title="Tailwind CSS trong dự án thật",
        subtitle="Utility-first, design token và cách giữ giao diện nhất quán khi dự án lớn",
        description=(
            "Không dừng ở cú pháp utility: khóa học bàn cách đặt design token, "
            "khi nào nên tách thành component và làm sao để một dự án nhiều "
            "người không biến thành hàng nghìn class rời rạc."
        ),
        category_slug="frontend",
        instructor_email=MAI_ANH,
        level="intermediate",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="typescript-cho-nguoi-da-viet-javascript",
        title="TypeScript cho người đã viết JavaScript",
        subtitle="Kiểu dữ liệu, generic và cách đọc thông báo lỗi dài ba màn hình",
        description=(
            "Dành cho người viết JavaScript thành thạo và muốn thêm kiểu vào "
            "code sẵn có. Phần khó nhất — đọc hiểu thông báo lỗi của trình "
            "kiểm tra kiểu — được dạy hẳn thành một chương."
        ),
        category_slug="frontend",
        instructor_email=KHOA,
        level="intermediate",
        price=Decimal("399000"),
    ),
    SyntheticCourseSpec(
        slug="nextjs-render-phia-may-chu-va-toi-uu-toc-do",
        title="Next.js: render phía máy chủ và tối ưu tốc độ",
        subtitle="App Router, server component và những con số Core Web Vitals đo được",
        description=(
            "Khóa học giải thích ranh giới giữa server component và client "
            "component, rồi đo tác động của từng lựa chọn lên thời gian tải "
            "thật thay vì nói chung chung là 'nhanh hơn'."
        ),
        category_slug="frontend",
        instructor_email=MAI_ANH,
        level="advanced",
        price=Decimal("499000"),
    ),
    SyntheticCourseSpec(
        slug="html-css-hien-dai-flexbox-grid-va-responsive",
        title="HTML/CSS hiện đại: Flexbox, Grid và responsive",
        subtitle="Dựng bố cục không cần framework, chạy đúng từ điện thoại tới màn hình rộng",
        description=(
            "Bắt đầu từ HTML có ngữ nghĩa, rồi tới Flexbox và Grid. Học xong "
            "dựng được bố cục của hầu hết trang web thường gặp mà không cần "
            "tới một thư viện CSS nào."
        ),
        category_slug="frontend",
        instructor_email=KHOA,
        level="beginner",
        price=Decimal("0"),
    ),
    # --- Backend -----------------------------------------------------------
    SyntheticCourseSpec(
        slug="postgresql-cho-lap-trinh-vien-ung-dung",
        title="PostgreSQL cho lập trình viên ứng dụng",
        subtitle="Index, transaction và cách đọc EXPLAIN để biết truy vấn chậm ở đâu",
        description=(
            "Không phải khóa quản trị CSDL. Đây là những gì người viết ứng dụng "
            "cần: thiết kế bảng, chọn index, hiểu mức cô lập của transaction và "
            "đọc được EXPLAIN ANALYZE khi một trang bỗng chậm."
        ),
        category_slug="backend",
        instructor_email=KHOA,
        level="intermediate",
        price=Decimal("399000"),
    ),
    SyntheticCourseSpec(
        slug="docker-va-docker-compose-cho-moi-truong-phat-trien",
        title="Docker và Docker Compose cho môi trường phát triển",
        subtitle="Đóng gói ứng dụng, dựng stack nhiều service, và vì sao build lại chậm",
        description=(
            "Từ Dockerfile đầu tiên tới một stack nhiều service chạy bằng một "
            "lệnh. Có hẳn một chương về cache layer — lý do thường gặp nhất "
            "khiến một lần build mất mười phút thay vì mười giây."
        ),
        category_slug="backend",
        instructor_email=KHOA,
        level="intermediate",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="thiet-ke-rest-api-va-tai-lieu-openapi",
        title="Thiết kế REST API và tài liệu OpenAPI",
        subtitle="Đặt tên tài nguyên, phân trang, phiên bản và hợp đồng lỗi nhất quán",
        description=(
            "Phần khó của API không phải là viết endpoint mà là giữ cho nó "
            "nhất quán sau hai năm. Khóa học bàn quy ước đặt tên, phân trang, "
            "đánh phiên bản và một hợp đồng lỗi mà client xử lý được."
        ),
        category_slug="backend",
        instructor_email=MAI_ANH,
        level="intermediate",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="redis-cache-hang-doi-va-gioi-han-truy-cap",
        title="Redis: cache, hàng đợi và giới hạn truy cập",
        subtitle="Khi nào nên cache, khi nào không, và cách hết hạn dữ liệu cho đúng",
        description=(
            "Redis dễ dùng sai vì nó dễ dùng. Khóa học đi qua cache-aside, "
            "hàng đợi công việc, rate limit và câu hỏi khó nhất trong cả ba: "
            "dữ liệu này cũ tới mức nào thì không còn dùng được."
        ),
        category_slug="backend",
        instructor_email=KHOA,
        level="advanced",
        price=Decimal("499000"),
    ),
    SyntheticCourseSpec(
        slug="kiem-thu-backend-voi-pytest",
        title="Kiểm thử backend với pytest",
        subtitle="Fixture, test có CSDL thật, và bộ test chạy đủ nhanh để người ta chịu chạy",
        description=(
            "Viết test cho code có CSDL và có gọi mạng, mà không biến mọi thứ "
            "thành mock. Gồm cả cách giữ bộ test chạy trong vài chục giây — "
            "bộ test chậm là bộ test không ai chạy."
        ),
        category_slug="backend",
        instructor_email=MAI_ANH,
        level="intermediate",
        price=Decimal("0"),
    ),
    # --- Python & dữ liệu --------------------------------------------------
    SyntheticCourseSpec(
        slug="python-nang-cao-decorator-generator-context-manager",
        title="Python nâng cao: decorator, generator và context manager",
        subtitle="Ba thứ khiến code người khác khó đọc, cho tới khi bạn tự viết được",
        description=(
            "Dành cho người đã viết Python được một thời gian. Mỗi chủ đề bắt "
            "đầu từ đoạn code lặp lại mà nó sinh ra để giải quyết, nên cú pháp "
            "đến sau lý do, không phải ngược lại."
        ),
        category_slug="python",
        instructor_email=KHOA,
        level="advanced",
        price=Decimal("499000"),
    ),
    SyntheticCourseSpec(
        slug="pandas-va-numpy-cho-xu-ly-du-lieu",
        title="Pandas và NumPy cho xử lý dữ liệu",
        subtitle="Đọc, làm sạch, nhóm và nối dữ liệu — trên tập lớn hơn bộ nhớ một chút",
        description=(
            "Đi từ một file CSV bẩn tới một bảng dùng được: thiếu giá trị, sai "
            "kiểu, trùng dòng. Phần cuối bàn cách xử lý tập dữ liệu lớn hơn "
            "RAM bằng cách đọc theo khối."
        ),
        category_slug="python",
        instructor_email=MAI_ANH,
        level="intermediate",
        price=Decimal("399000"),
    ),
    SyntheticCourseSpec(
        slug="truc-quan-hoa-du-lieu-voi-matplotlib",
        title="Trực quan hóa dữ liệu với Matplotlib",
        subtitle="Vẽ biểu đồ đọc được, và biết khi nào một biểu đồ đang nói dối",
        description=(
            "Nửa đầu là kỹ thuật vẽ; nửa sau là chọn loại biểu đồ và tránh "
            "những cách trình bày khiến số liệu trông khác sự thật — trục bị "
            "cắt, tỉ lệ sai, màu đánh lừa."
        ),
        category_slug="python",
        instructor_email=MAI_ANH,
        level="beginner",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="tu-dong-hoa-cong-viec-hang-ngay-bang-python",
        title="Tự động hóa công việc hằng ngày bằng Python",
        subtitle="Đọc file, gọi API, xử lý bảng tính và hẹn giờ chạy",
        description=(
            "Những việc lặp đi lặp lại mà ai cũng có: đổi tên hàng trăm file, "
            "gộp vài chục bảng tính, lấy dữ liệu từ một API rồi gửi báo cáo. "
            "Mỗi chương là một script chạy được ngay."
        ),
        category_slug="python",
        instructor_email=KHOA,
        level="beginner",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="nhap-mon-hoc-may-voi-scikit-learn",
        title="Nhập môn học máy với scikit-learn",
        subtitle="Hồi quy, phân loại, và cách đánh giá mô hình mà không tự lừa mình",
        description=(
            "Các thuật toán cơ bản, nhưng trọng tâm là phần người mới hay bỏ "
            "qua: chia tập dữ liệu, kiểm định chéo, và vì sao độ chính xác cao "
            "trên tập huấn luyện thường là tin xấu."
        ),
        category_slug="python",
        instructor_email=KHOA,
        level="intermediate",
        price=Decimal("499000"),
    ),
    # --- Khoa học máy tính -------------------------------------------------
    SyntheticCourseSpec(
        slug="quy-hoach-dong-qua-20-bai-toan",
        title="Quy hoạch động qua 20 bài toán",
        subtitle="Từ nhận ra bài toán con trùng nhau tới viết được công thức truy hồi",
        description=(
            "Hai mươi bài toán xếp theo độ khó tăng dần, mỗi bài đi từ lời "
            "giải vét cạn tới bản tối ưu. Mục tiêu là nhận ra dạng bài, không "
            "phải học thuộc lời giải."
        ),
        category_slug="cau-truc-du-lieu-giai-thuat",
        instructor_email=KHOA,
        level="advanced",
        price=Decimal("499000"),
    ),
    SyntheticCourseSpec(
        slug="do-thi-va-cac-thuat-toan-duyet",
        title="Đồ thị và các thuật toán duyệt",
        subtitle="BFS, DFS, đường đi ngắn nhất và cây khung nhỏ nhất",
        description=(
            "Biểu diễn đồ thị, rồi các thuật toán duyệt và tìm đường. Mỗi "
            "thuật toán gắn với một bài toán thật — lịch học, mạng máy tính, "
            "bản đồ — để biết khi nào dùng cái nào."
        ),
        category_slug="cau-truc-du-lieu-giai-thuat",
        instructor_email=MAI_ANH,
        level="advanced",
        price=Decimal("399000"),
    ),
    SyntheticCourseSpec(
        slug="luyen-phong-van-thuat-toan-trong-30-ngay",
        title="Luyện phỏng vấn thuật toán trong 30 ngày",
        subtitle="Lộ trình mỗi ngày một chủ đề, kèm cách trình bày lời giải khi bị hỏi",
        description=(
            "Lộ trình ba mươi ngày, mỗi ngày một dạng bài và một bài luyện. "
            "Có riêng phần nói thành lời lập luận của mình — thứ quyết định "
            "kết quả phỏng vấn ngang với việc giải được bài."
        ),
        category_slug="cau-truc-du-lieu-giai-thuat",
        instructor_email=MAI_ANH,
        level="intermediate",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="do-phuc-tap-va-toi-uu-ma-nguon",
        title="Độ phức tạp và tối ưu mã nguồn",
        subtitle="Đo trước khi tối ưu: profiler, big-O và khoảng cách giữa hai thứ đó",
        description=(
            "Big-O nói về xu hướng, profiler nói về máy của bạn, và hai câu "
            "trả lời thường khác nhau. Khóa học dạy dùng cả hai, theo đúng thứ "
            "tự: đo, rồi mới sửa."
        ),
        category_slug="cau-truc-du-lieu-giai-thuat",
        instructor_email=KHOA,
        level="intermediate",
        price=Decimal("0"),
    ),
    SyntheticCourseSpec(
        slug="he-dieu-hanh-tien-trinh-luong-va-bo-nho",
        title="Hệ điều hành: tiến trình, luồng và bộ nhớ",
        subtitle="Những gì xảy ra bên dưới khi chương trình của bạn chạy",
        description=(
            "Tiến trình và luồng, lập lịch, bộ nhớ ảo và vào/ra. Kiến thức nền "
            "giải thích vì sao code chạy nhanh trên máy này mà chậm trên máy "
            "khác, và vì sao container lại nhẹ đến vậy."
        ),
        category_slug="cau-truc-du-lieu-giai-thuat",
        instructor_email=MAI_ANH,
        level="advanced",
        price=Decimal("0"),
    ),
]


#: The four real courses `scripts.seed` writes. Each anchors one cluster, so
#: the synthetic histories reach into the catalogue the demo actually shows.
ANCHORS = {
    "frontend": "javascript-hien-dai-es6-va-dom",
    "backend": "xay-dung-rest-api-voi-fastapi",
    "python": "python-co-ban-cho-nguoi-moi-bat-dau",
    "cs": "cau-truc-du-lieu-va-giai-thuat-voi-python",
}

CLUSTER_NAMES = {
    "frontend": "Lập trình giao diện web",
    "backend": "Lập trình phía máy chủ",
    "python": "Python và dữ liệu",
    "cs": "Nền tảng khoa học máy tính",
}

#: Which cluster each synthetic course belongs to, by the category it is filed
#: under. The categories come from `scripts.seed`'s tree; the clusters are a
#: layer above them, because "Python và dữ liệu" is an interest while `python`
#: is a shelf in the catalogue.
CLUSTER_OF_CATEGORY = {
    "frontend": "frontend",
    "backend": "backend",
    "python": "python",
    "cau-truc-du-lieu-giai-thuat": "cs",
}


def _build_clusters() -> list[ClusterSpec]:
    clusters = []
    for category_slug, key in CLUSTER_OF_CATEGORY.items():
        slugs = [ANCHORS[key]] + [
            course.slug
            for course in SYNTHETIC_COURSES
            if course.category_slug == category_slug
        ]
        clusters.append(
            ClusterSpec(key=key, name=CLUSTER_NAMES[key], course_slugs=tuple(slugs))
        )
    return clusters


CLUSTERS = _build_clusters()

_CLUSTER_OF_SLUG = {
    slug: cluster.key for cluster in CLUSTERS for slug in cluster.course_slugs
}


def cluster_of(course_slug: str) -> str | None:
    """Which interest a course belongs to, or None if it is outside the data.

    Returns None rather than raising: a development database holds courses
    somebody made by hand, and a recommendation is allowed to land on one.
    """
    return _CLUSTER_OF_SLUG.get(course_slug)


def learner_password() -> str:
    return os.getenv("SEED_LEARNER_PASSWORD", DEFAULT_LEARNER_PASSWORD)


def build_population(seed: int = DEFAULT_SEED) -> list[LearnerPlan]:
    """Every learner and everything they did, decided here and nowhere else.

    Pure: no database, no clock, no global random state. The whole dataset is
    a function of `seed`, so the evaluation it feeds can be reproduced by
    anybody who runs this with the same number.
    """
    rng = random.Random(seed)
    per_cluster = LEARNER_COUNT // len(CLUSTERS)
    outsiders_of = {
        cluster.key: [
            slug
            for other in CLUSTERS
            if other.key != cluster.key
            for slug in other.course_slugs
        ]
        for cluster in CLUSTERS
    }

    learners: list[LearnerPlan] = []

    for cluster_index, cluster in enumerate(CLUSTERS):
        pool = list(cluster.course_slugs)

        for position in range(per_cluster):
            index = cluster_index * per_cluster + position

            # One course is assigned rather than drawn, rotating through the
            # cluster. With at least as many learners per cluster as there are
            # courses in it, this is what guarantees no course is left with no
            # takers -- and a course nobody has taken can never be recommended,
            # so it would cost precision@k for a reason that is not the model's.
            required = pool[position % len(pool)]
            rest = [slug for slug in pool if slug != required]
            drawn = rng.sample(rest, rng.randint(IN_CLUSTER_MIN, IN_CLUSTER_MAX) - 1)

            items = [
                _item(rng, slug, inside=True) for slug in sorted([required, *drawn])
            ]

            if rng.random() < NOISE_PROBABILITY:
                items.append(
                    _item(rng, rng.choice(outsiders_of[cluster.key]), inside=False)
                )

            learners.append(
                LearnerPlan(
                    email=f"hocvien{index + 1:02d}@{LEARNER_DOMAIN}",
                    full_name=(
                        f"{SURNAMES[index % len(SURNAMES)]} "
                        f"{GIVEN_NAMES[(index * 7) % len(GIVEN_NAMES)]}"
                    ),
                    cluster_key=cluster.key,
                    items=tuple(items),
                )
            )

    return learners


def _item(rng: random.Random, course_slug: str, *, inside: bool) -> ItemPlan:
    """One course in one learner's history.

    Completion and rating are drawn independently, and `interaction_weight`
    reconciles them -- a high rating outranks a completion, a low one cancels
    it. Drawing them separately rather than picking a weight directly is what
    makes this data exercise that function instead of assuming it.
    """
    completed = rng.random() < (
        COMPLETION_PROBABILITY if inside else NOISE_COMPLETION_PROBABILITY
    )
    rates = rng.random() < (
        RATING_PROBABILITY if inside else NOISE_RATING_PROBABILITY
    )
    rating = rng.choice(LIKED_RATINGS if inside else DISLIKED_RATINGS) if rates else None
    return ItemPlan(course_slug=course_slug, completed=completed, rating=rating)


def to_interactions(learners: list[LearnerPlan]) -> list[Interaction]:
    """The population as the recommender sees it, keyed by email and slug.

    Uses the service's own `interaction_weight`, so a test that fits a model on
    this is testing the weights the platform runs, not a copy of them.
    """
    return [
        Interaction(
            user_id=learner.email,
            course_id=item.course_slug,
            weight=interaction_weight(completed=item.completed, rating=item.rating),
        )
        for learner in learners
        for item in learner.items
    ]


# --- Writing it down -------------------------------------------------------


async def _ensure_courses(session: AsyncSession) -> tuple[dict[str, Course], int]:
    """Create any missing synthetic course; return every course by slug.

    The anchors are looked up, never created: they belong to `scripts.seed`,
    and quietly creating a second "Python cơ bản" here would leave the demo
    catalogue with two of them.
    """
    wanted = {course.slug for course in SYNTHETIC_COURSES} | set(ANCHORS.values())
    existing = {
        course.slug: course
        for course in await session.scalars(
            select(Course).where(Course.slug.in_(wanted))
        )
    }

    missing_anchors = sorted(set(ANCHORS.values()) - set(existing))
    if missing_anchors:
        raise SystemExit(
            "Chưa có các khóa học gốc: "
            + ", ".join(missing_anchors)
            + ". Chạy `python -m scripts.seed` trước."
        )

    created = 0
    for spec in SYNTHETIC_COURSES:
        if spec.slug in existing:
            continue
        existing[spec.slug] = await _build_course(session, spec)
        created += 1

    return existing, created


async def _build_course(session: AsyncSession, spec: SyntheticCourseSpec) -> Course:
    instructor = await session.scalar(
        select(User).where(User.email == spec.instructor_email)
    )
    category = await session.scalar(
        select(Category).where(Category.slug == spec.category_slug)
    )
    if instructor is None or category is None:
        raise SystemExit(
            f"Thiếu giảng viên hoặc danh mục cho {spec.slug}. "
            "Chạy `python -m scripts.seed` trước."
        )

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title=spec.title,
        slug=spec.slug,
        subtitle=spec.subtitle,
        description=spec.description,
        price=spec.price,
        level=spec.level,
        language="vi",
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()

    # One section, one article. Enough that a recommendation opens a page with
    # something on it; not so much that a fabricated course starts passing for
    # a real one.
    section = CourseSection(course_id=course.id, title="Giới thiệu khóa học", position=0)
    session.add(section)
    await session.flush()

    session.add(
        Lesson(
            section_id=section.id,
            title="Khóa học này dạy gì",
            type="article",
            position=0,
            is_preview=True,
            article_content=spec.description,
        )
    )
    await session.flush()
    return course


async def _ensure_learners(
    session: AsyncSession, population: list[LearnerPlan]
) -> tuple[dict[str, User], int]:
    emails = [learner.email for learner in population]
    existing = {
        user.email: user
        for user in await session.scalars(select(User).where(User.email.in_(emails)))
    }

    password_hash = hash_password(learner_password())
    created = 0
    for learner in population:
        if learner.email in existing:
            continue
        user = User(
            email=learner.email,
            full_name=learner.full_name,
            password_hash=password_hash,
            role="student",
        )
        session.add(user)
        existing[learner.email] = user
        created += 1

    await session.flush()
    return existing, created


async def seed_interactions(
    session: AsyncSession, population: list[LearnerPlan]
) -> Written:
    """Write the population, skipping anything already there.

    Does not commit: the caller decides, which is what lets the tests run this
    inside a transaction they roll back.
    """
    courses, courses_created = await _ensure_courses(session)
    learners, learners_created = await _ensure_learners(session, population)

    enrolled_rows = await session.execute(
        select(Enrollment.user_id, Enrollment.course_id, Enrollment.completed_at)
    )
    enrolled = {(user_id, course_id): done for user_id, course_id, done in enrolled_rows}
    reviewed = {
        (user_id, course_id)
        for user_id, course_id in await session.execute(
            select(Review.user_id, Review.course_id)
        )
    }

    now = datetime.now(UTC)
    enrollments_created = 0
    reviews_created = 0
    touched: set = set()

    for learner in population:
        user = learners[learner.email]
        for item in learner.items:
            course = courses[item.course_slug]
            touched.add(course.id)
            key = (user.id, course.id)

            if key not in enrolled:
                session.add(
                    Enrollment(
                        user_id=user.id,
                        course_id=course.id,
                        completed_at=now if item.completed else None,
                    )
                )
                enrolled[key] = now if item.completed else None
                enrollments_created += 1

            if item.rating is not None and key not in reviewed:
                session.add(
                    Review(user_id=user.id, course_id=course.id, rating=item.rating)
                )
                reviewed.add(key)
                reviews_created += 1

    await session.flush()
    await _refresh_course_stats(session, touched)

    return Written(
        courses=courses_created,
        learners=learners_created,
        enrollments=enrollments_created,
        reviews=reviews_created,
    )


async def _refresh_course_stats(session: AsyncSession, course_ids: set) -> None:
    """Recompute the denormalised counters for the courses just touched.

    `courses.students_count`, `rating_avg` and `rating_count` are maintained by
    the enrolment and review services, and this script writes rows without
    going through either. Recomputing from the rows themselves is also what
    makes `--purge` able to put the real courses back as they were.
    """
    if not course_ids:
        return

    students = (
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.course_id == Course.id)
        .scalar_subquery()
    )
    ratings = (
        select(func.count())
        .select_from(Review)
        .where(Review.course_id == Course.id)
        .scalar_subquery()
    )
    average = (
        select(func.coalesce(func.round(func.avg(Review.rating), 2), 0))
        .select_from(Review)
        .where(Review.course_id == Course.id)
        .scalar_subquery()
    )

    await session.execute(
        update(Course)
        .where(Course.id.in_(course_ids))
        .values(students_count=students, rating_count=ratings, rating_avg=average)
        .execution_options(synchronize_session=False)
    )


async def purge(session: AsyncSession) -> tuple[int, int]:
    """Remove every row this script creates. Returns (courses, learners).

    Twenty synthetic courses are what makes the recommender measurable and
    what makes the catalogue page look padded. Being able to take them out
    again -- and leave the four real courses with the student counts they
    actually had -- is the difference between seed data and contamination.
    """
    slugs = [course.slug for course in SYNTHETIC_COURSES]
    course_ids = list(
        await session.scalars(select(Course.id).where(Course.slug.in_(slugs)))
    )
    learner_ids = list(
        await session.scalars(
            select(User.id).where(User.email.like(f"%@{LEARNER_DOMAIN}"))
        )
    )

    if course_ids:
        # Enrolments point at courses with ON DELETE RESTRICT, and by now a
        # real account may have enrolled in one of these by hand.
        await session.execute(
            delete(Review).where(Review.course_id.in_(course_ids))
        )
        await session.execute(
            delete(Enrollment).where(Enrollment.course_id.in_(course_ids))
        )

    # Deleting the learners cascades whatever they did to the real courses too.
    if learner_ids:
        await session.execute(delete(User).where(User.id.in_(learner_ids)))

    if course_ids:
        await session.execute(delete(Course).where(Course.id.in_(course_ids)))

    await session.flush()

    anchors = set(
        await session.scalars(
            select(Course.id).where(Course.slug.in_(list(ANCHORS.values())))
        )
    )
    await _refresh_course_stats(session, anchors)

    return len(course_ids), len(learner_ids)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Xóa toàn bộ khóa học và học viên giả lập do script này tạo ra.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Hạt giống ngẫu nhiên (mặc định {DEFAULT_SEED}).",
    )
    args = parser.parse_args()

    async with SessionLocal() as session:
        if args.purge:
            courses, learners = await purge(session)
            await session.commit()
            print(f"Đã xóa {courses} khóa học giả lập và {learners} học viên giả lập.")
            return

        population = build_population(args.seed)
        written = await seed_interactions(session, population)
        await session.commit()

    print(f"hạt giống  : {args.seed}")
    print(f"khóa học   : {written.courses} tạo mới")
    print(f"học viên   : {written.learners} tạo mới")
    print(f"đăng ký    : {written.enrollments} tạo mới")
    print(f"đánh giá   : {written.reviews} tạo mới")
    print(f"tổng tương tác trong kế hoạch: {len(to_interactions(population))}")

    if written.learners and "SEED_LEARNER_PASSWORD" not in os.environ:
        print(
            f"\nWARNING: {written.learners} tài khoản học viên dùng mật khẩu mặc định "
            f"{DEFAULT_LEARNER_PASSWORD!r}. Đặt SEED_LEARNER_PASSWORD trước khi seed "
            "vào bất cứ CSDL nào truy cập được từ internet.",
            file=sys.stderr,
        )

    print("\nChạy `python -m scripts.rebuild_recommendations` để tính lại gợi ý.")


if __name__ == "__main__":
    asyncio.run(main())
