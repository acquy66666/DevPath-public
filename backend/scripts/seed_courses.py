"""Real courses for the seeded database: four programming courses, with the
sections, lessons and video assets that make them look like courses rather
than like fixtures.

Everything after this point in the project demos on this data -- search,
enrolment, the player, progress, notes, reviews, and later the recommender and
the RAG chatbot -- which is why the titles and the article text are written to
be read, not filled with lorem ipsum.

**The video is somebody else's.** Each video lesson points at one public HLS
sample stream, the one hls.js uses in its own demo, so the courses play on a
machine with no R2 bucket configured. Set `SEED_SAMPLE_HLS_URL` to point the
seed at your own manifest instead. Nothing here uploads anything: a real
upload goes through the presigned-URL flow and the transcode worker, and a
seed script is not the place to imitate that.

Idempotent by course slug: a course that is already there is left exactly as
it is, including any edits somebody made to it by hand.
"""

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    Category,
    CodeExercise,
    Course,
    CourseSection,
    Lesson,
    TestCase,
    User,
    VideoAsset,
)
from app.services import course_stats

# hls.js's own demo stream: a short Big Buck Bunny render with several
# renditions, so the quality switch in the player has something to switch.
DEFAULT_SAMPLE_HLS_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

DEFAULT_INSTRUCTOR_PASSWORD = "devpath-instructor"


def sample_hls_url() -> str:
    return os.getenv("SEED_SAMPLE_HLS_URL", DEFAULT_SAMPLE_HLS_URL).strip()


@dataclass(frozen=True, slots=True)
class InstructorSpec:
    email: str
    full_name: str


@dataclass(frozen=True, slots=True)
class TestCaseSpec:
    input: str
    expected_output: str
    hidden: bool = True
    weight: int = 1


@dataclass(frozen=True, slots=True)
class ExerciseSpec:
    """A code exercise and the cases that mark it.

    Samples first and visible, hidden cases after them. One list, in the order
    the student sees, because "case 3 failed" has to mean the third row here.
    """

    statement_md: str
    starter_code: str
    cases: list[TestCaseSpec]
    time_limit_ms: int = 2000
    memory_limit_mb: int = 128


@dataclass(frozen=True, slots=True)
class LessonSpec:
    title: str
    duration_s: int = 0
    """Video length in seconds. Zero marks an article, which has no timeline."""
    article: str | None = None
    preview: bool = False
    exercise: ExerciseSpec | None = None

    @property
    def type(self) -> str:
        if self.exercise is not None:
            return "code_exercise"
        return "article" if self.article is not None else "video"


@dataclass(frozen=True, slots=True)
class SectionSpec:
    title: str
    lessons: list[LessonSpec]


@dataclass(frozen=True, slots=True)
class CourseSpec:
    title: str
    slug: str
    subtitle: str
    description: str
    category_slug: str
    instructor_email: str
    level: str
    price: Decimal
    sections: list[SectionSpec] = field(default_factory=list)

    @property
    def duration_total_s(self) -> int:
        """What the course should add up to. The column itself is not written
        from this: the seed recounts it from the video rows it creates, through
        the same `course_stats` path a finished transcode takes."""
        return sum(
            lesson.duration_s
            for section in self.sections
            for lesson in section.lessons
        )


# `users` has no profile text yet, so an instructor here is a name and an
# account -- the course page shows exactly those two things.
KHOA = InstructorSpec(email="khoa.tran@devpath.example", full_name="Trần Minh Khoa")
MAI_ANH = InstructorSpec(email="mai.anh@devpath.example", full_name="Nguyễn Mai Anh")

INSTRUCTORS = [KHOA, MAI_ANH]


COURSES = [
    CourseSpec(
        title="Python cơ bản cho người mới bắt đầu",
        slug="python-co-ban-cho-nguoi-moi-bat-dau",
        subtitle="Từ dòng lệnh đầu tiên đến chương trình chạy được, không cần biết gì trước",
        description=(
            "Khóa học dành cho người chưa từng viết một dòng code nào. Bạn sẽ cài đặt "
            "môi trường, viết chương trình đầu tiên, rồi đi qua biến, kiểu dữ liệu, "
            "rẽ nhánh, vòng lặp và hàm — mỗi phần đều kèm ví dụ chạy được ngay.\n\n"
            "Điều khóa học này chú trọng khác với phần lớn khóa nhập môn: đọc hiểu "
            "thông báo lỗi. Người mới bỏ cuộc phần lớn vì gặp lỗi mà không biết máy "
            "đang nói gì, nên đó là bài học thứ ba chứ không phải phụ lục cuối khóa."
        ),
        category_slug="python",
        instructor_email=KHOA.email,
        level="beginner",
        price=Decimal("0"),
        sections=[
            SectionSpec(
                title="Bắt đầu với Python",
                lessons=[
                    LessonSpec("Cài đặt Python và VS Code", 512, preview=True),
                    LessonSpec("Chương trình đầu tiên: Hello, World!", 386),
                    LessonSpec(
                        "Đọc hiểu thông báo lỗi",
                        article=(
                            "Thông báo lỗi của Python đọc từ **dưới lên**. Dòng cuối "
                            "cùng cho biết chuyện gì xảy ra, các dòng phía trên cho "
                            "biết nó xảy ra ở đâu — đó là traceback, tức là đường đi "
                            "của lời gọi hàm dẫn tới chỗ hỏng.\n\n"
                            "Ba lỗi bạn sẽ gặp nhiều nhất trong tuần đầu:\n\n"
                            "- `SyntaxError` — Python không hiểu câu lệnh. Thường là "
                            "thiếu dấu hai chấm, thiếu ngoặc đóng, hoặc lẫn dấu nháy.\n"
                            "- `NameError` — bạn dùng một tên chưa được gán. Hay gặp "
                            "khi gõ sai tên biến, hoặc dùng biến trước dòng tạo ra nó.\n"
                            "- `IndentationError` — thụt lề không đều. Chọn 4 dấu cách "
                            "và để editor thay tab bằng dấu cách là hết.\n\n"
                            "Thói quen đáng tập ngay từ hôm nay: đọc trọn thông báo "
                            "trước khi sửa bất cứ thứ gì. Phần lớn thời gian nó đã nói "
                            "chính xác dòng nào sai và sai cái gì."
                        ),
                    ),
                ],
            ),
            SectionSpec(
                title="Biến, kiểu dữ liệu và toán tử",
                lessons=[
                    LessonSpec("Biến và phép gán", 445),
                    LessonSpec("Số, chuỗi và boolean", 623),
                    LessonSpec("f-string: ghép chuỗi cho người đọc", 371),
                    LessonSpec(
                        "Ép kiểu và những cái bẫy quen thuộc",
                        article=(
                            "`input()` luôn trả về chuỗi. Đây là nguồn gốc của lỗi "
                            "kinh điển nhất khi mới học: `input(\"Tuổi: \") + 1` không "
                            "cộng được, vì bạn đang cộng một chuỗi với một số.\n\n"
                            "`int(\"12\")` cho ra 12, nhưng `int(\"12.5\")` thì lỗi — "
                            "phải qua `float` trước. Và `int(12.9)` cho 12 chứ không "
                            "phải 13: nó cắt phần thập phân, không làm tròn. Muốn làm "
                            "tròn thì dùng `round()`.\n\n"
                            "Cái bẫy cuối, gặp ở mọi ngôn ngữ chứ không riêng Python: "
                            "`0.1 + 0.2` không bằng `0.3`. Số thực trong máy tính là "
                            "xấp xỉ nhị phân. Khi làm việc với tiền, dùng `Decimal` — "
                            "đúng như cột giá trong chính hệ thống bạn đang học trên đó."
                        ),
                    ),
                ],
            ),
            SectionSpec(
                title="Rẽ nhánh và vòng lặp",
                lessons=[
                    LessonSpec("Câu lệnh if / elif / else", 534),
                    LessonSpec("Vòng lặp for và range", 498),
                    LessonSpec("Vòng lặp while và điều kiện dừng", 452),
                    LessonSpec("break, continue và vòng lặp lồng nhau", 587),
                    LessonSpec(
                        "Bài tập: đếm số chẵn",
                        exercise=ExerciseSpec(
                            statement_md=(
                                "Cho một dãy số nguyên, đếm xem có bao nhiêu số "
                                "chẵn.\n\n"
                                "**Đầu vào:** dòng đầu là số nguyên `n` — số lượng "
                                "phần tử. Dòng thứ hai là `n` số nguyên cách nhau "
                                "bởi dấu cách.\n\n"
                                "**Đầu ra:** một số nguyên duy nhất — số lượng số "
                                "chẵn trong dãy.\n\n"
                                "**Giới hạn:** `1 ≤ n ≤ 1000`, mỗi số trong khoảng "
                                "`-10^6` đến `10^6`.\n\n"
                                "**Ví dụ**\n\n"
                                "```\n5\n1 2 3 4 6\n```\n\n"
                                "cho kết quả `3`, vì dãy có ba số chẵn là 2, 4 và 6."
                            ),
                            starter_code=(
                                "n = int(input())\n"
                                "numbers = list(map(int, input().split()))\n"
                                "\n"
                                "# Viết code của bạn ở đây\n"
                            ),
                            cases=[
                                # Two samples: the worked example from the
                                # statement, and one answering the question every
                                # beginner has -- what if there are none?
                                TestCaseSpec("5\n1 2 3 4 6\n", "3\n", hidden=False),
                                TestCaseSpec("3\n1 3 5\n", "0\n", hidden=False),
                                # Hidden. One element; all even; negatives, which
                                # an answer written as `% 2 == 1` gets wrong; and
                                # zero, which is even and routinely forgotten.
                                TestCaseSpec("1\n2\n", "1\n"),
                                TestCaseSpec("4\n2 4 6 8\n", "4\n"),
                                TestCaseSpec("5\n-2 -3 -4 -5 -6\n", "3\n", weight=2),
                                TestCaseSpec("3\n0 1 2\n", "2\n", weight=2),
                            ],
                        ),
                    ),
                ],
            ),
            SectionSpec(
                title="Hàm và tổ chức code",
                lessons=[
                    LessonSpec("Định nghĩa hàm, tham số, giá trị trả về", 641),
                    LessonSpec("Tham số mặc định và tham số từ khóa", 476),
                    LessonSpec(
                        "Phạm vi biến: local, global và vì sao nên tránh global",
                        article=(
                            "Biến tạo bên trong một hàm chỉ sống trong hàm đó. Ra khỏi "
                            "hàm là nó biến mất, và đó là tính năng chứ không phải hạn "
                            "chế: nhờ vậy hai hàm có thể cùng đặt tên biến `i` mà không "
                            "giẫm lên nhau.\n\n"
                            "Từ khóa `global` cho phép hàm ghi đè biến bên ngoài. Nó "
                            "chạy được, và gần như luôn là ý tồi. Một hàm sửa trạng "
                            "thái ở đâu đó ngoài tầm nhìn là hàm mà bạn phải đọc hết "
                            "mới đoán được nó làm gì. Truyền giá trị vào qua tham số và "
                            "trả kết quả ra qua `return` — hàm khi ấy kiểm thử được, "
                            "và đọc một mình cũng hiểu.\n\n"
                            "Quy tắc bỏ túi: nếu phải dùng `global` để chương trình "
                            "chạy, gần như chắc chắn là hàm đang ôm quá nhiều việc."
                        ),
                    ),
                    LessonSpec("Chia chương trình thành nhiều file", 519),
                ],
            ),
        ],
    ),
    CourseSpec(
        title="JavaScript hiện đại: ES6+ và DOM",
        slug="javascript-hien-dai-es6-va-dom",
        subtitle="Cú pháp hiện đại, thao tác DOM và bất đồng bộ — đủ để tự làm giao diện động",
        description=(
            "Khóa học dành cho người đã biết một ngôn ngữ bất kỳ và muốn viết "
            "JavaScript như năm 2026 chứ không phải như năm 2010. Bắt đầu từ let/const "
            "và arrow function, đi qua DOM và sự kiện, kết thúc ở async/await và fetch.\n\n"
            "Mỗi chương đóng lại bằng một bài thực hành nhỏ có thể mở trong trình duyệt "
            "và xem kết quả ngay, không cần dựng dự án hay cài công cụ build."
        ),
        category_slug="javascript",
        instructor_email=MAI_ANH.email,
        level="beginner",
        price=Decimal("0"),
        sections=[
            SectionSpec(
                title="Nền tảng ES6+",
                lessons=[
                    LessonSpec("let, const và vì sao var đã lùi lại", 468, preview=True),
                    LessonSpec("Arrow function và giá trị của this", 592),
                    LessonSpec("Destructuring, spread và rest", 545),
                    LessonSpec("Template literal và optional chaining", 402),
                ],
            ),
            SectionSpec(
                title="Làm việc với DOM",
                lessons=[
                    LessonSpec("Chọn phần tử: querySelector và bạn bè", 431),
                    LessonSpec("Thay đổi nội dung, thuộc tính và class", 507),
                    LessonSpec("Sự kiện và event delegation", 638),
                    LessonSpec(
                        "Form và kiểm tra dữ liệu phía client",
                        article=(
                            "Kiểm tra dữ liệu ở trình duyệt là để người dùng biết mình "
                            "gõ sai ngay lập tức, **không phải** để bảo vệ hệ thống. "
                            "Mọi thứ chạy trong trình duyệt đều sửa được, nên máy chủ "
                            "vẫn phải kiểm tra lại đúng những điều kiện đó. Xem lại "
                            "cách backend của chính trang này làm: Pydantic kiểm tra "
                            "mọi request, bất kể form đã kiểm tra hay chưa.\n\n"
                            "HTML làm sẵn cho bạn nhiều hơn bạn tưởng: `required`, "
                            "`type=\"email\"`, `minlength`, `pattern` đều chạy mà không "
                            "cần một dòng JavaScript. Chỉ viết tay phần HTML không diễn "
                            "đạt được — ví dụ \"mật khẩu nhập lại phải trùng\".\n\n"
                            "Và hãy báo lỗi ở cạnh ô nhập, ngay khi người dùng rời ô đó. "
                            "Một danh sách lỗi ở đầu trang sau khi bấm gửi là cách chắc "
                            "chắn nhất để người ta bỏ dở biểu mẫu."
                        ),
                    ),
                ],
            ),
            SectionSpec(
                title="Bất đồng bộ và gọi API",
                lessons=[
                    LessonSpec("Từ callback tới Promise", 573),
                    LessonSpec("async / await và cách bắt lỗi cho đúng", 611),
                    LessonSpec("fetch: gọi API và đọc kết quả", 556),
                    LessonSpec("Hiển thị trạng thái đang tải và trạng thái lỗi", 488),
                ],
            ),
        ],
    ),
    CourseSpec(
        title="Xây dựng REST API với FastAPI",
        slug="xay-dung-rest-api-voi-fastapi",
        subtitle="Từ endpoint đầu tiên đến API có xác thực, có test và đóng gói Docker",
        description=(
            "Khóa học thực hành: xây một API đặt lịch từ con số không, đi hết vòng đời "
            "một tính năng — model, migration, service, endpoint, test.\n\n"
            "Trọng tâm là phân lớp. Router chỉ nhận request và trả response, business "
            "logic nằm ở service, truy cập dữ liệu nằm ở model. Nghe thì hiển nhiên, "
            "nhưng đây là ranh giới bị phá đầu tiên khi dự án gấp, và là lý do một dự "
            "án sáu tháng tuổi trở nên khó sửa."
        ),
        category_slug="backend",
        instructor_email=MAI_ANH.email,
        level="intermediate",
        price=Decimal("0"),
        sections=[
            SectionSpec(
                title="Khởi động dự án",
                lessons=[
                    LessonSpec("FastAPI trong 10 phút", 604, preview=True),
                    LessonSpec("Cấu trúc thư mục và router", 522),
                    LessonSpec("Pydantic v2: kiểm tra dữ liệu vào và ra", 668),
                ],
            ),
            SectionSpec(
                title="Cơ sở dữ liệu",
                lessons=[
                    LessonSpec("SQLAlchemy 2.x bất đồng bộ", 715),
                    LessonSpec("Alembic: mọi thay đổi schema đều qua migration", 583),
                    LessonSpec("Quan hệ, khóa ngoại và ON DELETE", 627),
                    LessonSpec(
                        "Vì sao router không được chứa business logic",
                        article=(
                            "Một endpoint làm ba việc: đọc request, ra quyết định, ghi "
                            "kết quả. Chỉ việc thứ hai là thứ đáng kiểm thử, và nó là "
                            "việc duy nhất không cần biết HTTP.\n\n"
                            "Khi logic nằm trong router, muốn kiểm thử nó bạn phải dựng "
                            "một request giả. Khi nó nằm trong service, bạn gọi một hàm "
                            "Python bình thường với một session và vài tham số. Khác "
                            "biệt đó nghe nhỏ cho tới lúc có ba mươi endpoint.\n\n"
                            "Ranh giới thực dụng: router được phép quyết định **mã "
                            "trạng thái**, service quyết định **chuyện gì đã xảy ra**. "
                            "Service ném ra một lỗi nghiệp vụ có mã riêng; một exception "
                            "handler dùng chung dịch nó thành 403 hay 409. Nhờ vậy mọi "
                            "lỗi của API có cùng một hình dạng, và frontend chỉ cần "
                            "nhìn vào mã lỗi chứ không đọc câu chữ."
                        ),
                    ),
                ],
            ),
            SectionSpec(
                title="Xác thực, kiểm thử và triển khai",
                lessons=[
                    LessonSpec("Băm mật khẩu và JWT access/refresh", 742),
                    LessonSpec("Phân quyền bằng dependency", 561),
                    LessonSpec("Viết test với pytest và httpx", 689),
                    LessonSpec("Đóng gói bằng Docker và chạy sau nginx", 634),
                ],
            ),
        ],
    ),
    CourseSpec(
        title="Cấu trúc dữ liệu & giải thuật với Python",
        slug="cau-truc-du-lieu-va-giai-thuat-voi-python",
        subtitle="Đủ để qua vòng phỏng vấn kỹ thuật, và để viết code nhanh hơn hằng ngày",
        description=(
            "Khóa học đi qua những cấu trúc dữ liệu và thuật toán xuất hiện nhiều nhất "
            "trong phỏng vấn lẫn trong công việc thật, cài đặt lại bằng Python rồi so "
            "sánh với thứ có sẵn trong thư viện chuẩn.\n\n"
            "Mỗi thuật toán đều kèm phần đo thời gian chạy trên dữ liệu lớn, để độ phức "
            "tạp không dừng ở ký hiệu trên giấy mà thành con số bạn nhìn thấy."
        ),
        category_slug="cau-truc-du-lieu-giai-thuat",
        instructor_email=KHOA.email,
        level="intermediate",
        price=Decimal("499000"),
        sections=[
            SectionSpec(
                title="Độ phức tạp thuật toán",
                lessons=[
                    LessonSpec("Big-O trong 15 phút", 903, preview=True),
                    LessonSpec(
                        "Đo thời gian chạy thật bằng timeit",
                        article=(
                            "Big-O nói về **xu hướng khi dữ liệu lớn dần**, không nói "
                            "cái nào nhanh hơn ở kích thước bạn đang có. Một thuật toán "
                            "O(n²) với hằng số nhỏ vẫn thắng một thuật toán O(n log n) "
                            "nặng nề khi n bằng vài chục — đó là lý do phần lớn hàm sort "
                            "trong thư viện chuẩn chuyển sang insertion sort cho mảng ngắn.\n\n"
                            "Cách đo đáng tin: chạy cùng một phép trên nhiều kích thước "
                            "đầu vào — 1.000, 10.000, 100.000 — rồi nhìn tỷ lệ thời gian. "
                            "Gấp mười đầu vào mà thời gian gấp mười là tuyến tính; gấp "
                            "một trăm là bậc hai.\n\n"
                            "Dùng `timeit` chứ đừng tự đo bằng `time.time()`: nó chạy "
                            "lại nhiều lần và lấy kết quả tốt nhất, nên nhiễu từ hệ điều "
                            "hành không lẫn vào con số."
                        ),
                    ),
                ],
            ),
            SectionSpec(
                title="Cấu trúc dữ liệu tuyến tính",
                lessons=[
                    LessonSpec("Mảng động: list của Python thật ra là gì", 656),
                    LessonSpec("Danh sách liên kết đơn và đôi", 748),
                    LessonSpec("Ngăn xếp, hàng đợi và deque", 592),
                    LessonSpec("Bảng băm: dict hoạt động thế nào", 811),
                ],
            ),
            SectionSpec(
                title="Thuật toán kinh điển",
                lessons=[
                    LessonSpec("Tìm kiếm nhị phân và các biến thể", 623),
                    LessonSpec("Merge sort và quick sort", 897),
                    LessonSpec("Cây nhị phân tìm kiếm và duyệt cây", 774),
                    LessonSpec("Quy hoạch động nhập môn", 936),
                ],
            ),
        ],
    ),
]


async def _instructor(session: AsyncSession, spec: InstructorSpec) -> tuple[User, bool]:
    """Create the instructor, or return the existing account untouched."""
    existing = await session.scalar(select(User).where(User.email == spec.email))
    if existing is not None:
        return existing, False

    password = os.getenv("SEED_INSTRUCTOR_PASSWORD", DEFAULT_INSTRUCTOR_PASSWORD)
    user = User(
        email=spec.email,
        full_name=spec.full_name,
        password_hash=hash_password(password),
        role="instructor",
    )
    session.add(user)
    await session.flush()
    return user, True


async def _build_course(
    session: AsyncSession,
    spec: CourseSpec,
    instructor: User,
    category: Category,
    hls_url: str,
) -> None:
    """Write one course and everything under it. Assumes it is not there yet."""
    published_at = datetime.now(UTC)

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
        published_at=published_at,
    )
    session.add(course)
    await session.flush()

    for section_position, section_spec in enumerate(spec.sections):
        section = CourseSection(
            course_id=course.id,
            title=section_spec.title,
            position=section_position,
        )
        session.add(section)
        await session.flush()

        for lesson_position, lesson_spec in enumerate(section_spec.lessons):
            video_asset_id = None

            if lesson_spec.type == "video":
                asset = VideoAsset(
                    # Deterministic, and unique per lesson because
                    # uq_video_assets_storage_key says it has to be. Nothing is
                    # actually stored under this key -- the manifest below is.
                    storage_key=(
                        f"seed/{spec.slug}/{section_position}-{lesson_position}.mp4"
                    ),
                    duration_s=lesson_spec.duration_s,
                    hls_manifest_key=hls_url,
                    status="ready",
                )
                session.add(asset)
                await session.flush()
                video_asset_id = asset.id

            lesson = Lesson(
                section_id=section.id,
                title=lesson_spec.title,
                type=lesson_spec.type,
                position=lesson_position,
                is_preview=lesson_spec.preview,
                video_asset_id=video_asset_id,
                article_content=lesson_spec.article,
            )
            session.add(lesson)

            if lesson_spec.exercise is not None:
                await session.flush()
                await _add_exercise(session, lesson, lesson_spec.exercise)

    # The catalogue prints the length, and a course showing none looks broken.
    await course_stats.recount_duration(session, course.id)


async def _add_exercise(
    session: AsyncSession, lesson: Lesson, spec: ExerciseSpec
) -> None:
    """Attach an exercise and its test cases to a freshly created lesson."""
    exercise = CodeExercise(
        lesson_id=lesson.id,
        statement_md=spec.statement_md,
        language="python",
        starter_code=spec.starter_code,
        time_limit_ms=spec.time_limit_ms,
        memory_limit_mb=spec.memory_limit_mb,
    )
    session.add(exercise)
    await session.flush()

    for position, case in enumerate(spec.cases):
        session.add(
            TestCase(
                exercise_id=exercise.id,
                input=case.input,
                expected_output=case.expected_output,
                is_hidden=case.hidden,
                position=position,
                score_weight=case.weight,
            )
        )


async def seed_courses(session: AsyncSession) -> tuple[int, int]:
    """Insert any course that is missing, matched by slug.

    Returns how many instructors and how many courses were created. A course
    already in the database is skipped whole -- not diffed, not repaired --
    because the person who changed it meant to.
    """
    instructors: dict[str, User] = {}
    instructors_created = 0

    for spec in INSTRUCTORS:
        user, created = await _instructor(session, spec)
        instructors[spec.email] = user
        instructors_created += int(created)

    hls_url = sample_hls_url()
    courses_created = 0

    for spec in COURSES:
        existing = await session.scalar(
            select(Course.id).where(Course.slug == spec.slug)
        )
        if existing is not None:
            continue

        category = await session.scalar(
            select(Category).where(Category.slug == spec.category_slug)
        )
        if category is None:
            # seed_categories runs first and creates every slug used here, so
            # this means the two lists have drifted apart.
            raise RuntimeError(
                f"Category {spec.category_slug!r} does not exist: CATEGORY_TREE "
                f"in scripts/seed.py and COURSES here have drifted apart."
            )

        await _build_course(
            session, spec, instructors[spec.instructor_email], category, hls_url
        )
        courses_created += 1

    return instructors_created, courses_created


__all__ = [
    "COURSES",
    "DEFAULT_INSTRUCTOR_PASSWORD",
    "DEFAULT_SAMPLE_HLS_URL",
    "INSTRUCTORS",
    "sample_hls_url",
    "seed_courses",
]
