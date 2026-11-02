"""More real courses, so the catalogue page has something to search through.

    python -m scripts.seed_catalogue
    python -m scripts.seed_catalogue --purge

`scripts.seed` writes four courses, and four courses make a poor catalogue:
every filter answers "one result" or "none", the search box finds the same
card for almost any word, and the category tree has five leaves with nothing
in half of them. This writes twenty-two more -- ten new categories, all three
levels, prices from free to 899.000 ₫ -- with titles, descriptions and lesson
text written to be read, so full-text search and the filters return results
that differ from one query to the next.

**Real, not synthetic.** `scripts.seed_interactions` also adds courses, but
those exist to measure the recommender: one outline lesson each, and the
thesis has to call them fabricated. These are demo content like the four in
`scripts.seed_courses`: two or three sections, video lessons on the same
public HLS sample stream, and article lessons with real explanations -- which
is also what the AI assistant reads once `scripts.ingest_course` has run.

**Built exactly like the real seed.** The same `CourseSpec` and the same
`_build_course` as `scripts.seed_courses`, so each course lands `published`
with the same rows an admin's approval leaves (approval writes no record of
its own beyond the status and `published_at`). Ids come from
`seed_course_id(slug)`, so every machine holds the same ids and the fallback
covers keep their colours. Only `published_at` is moved afterwards, spread
over the last months, so "Mới nhất" sorts into an order instead of a tie.

**Not part of `scripts.seed`** on purpose: the visual baselines in
`frontend/e2e/visual` are taken on a stack with only that, and twenty-two more
cards would move every catalogue screenshot.

Idempotent by slug, like the rest of the seed. `--purge` removes the courses,
their video rows and the categories it added (once empty). It refuses while an
order points at one of them -- an order is a money record and no seed script
deletes one; purge `scripts.seed_study` and `scripts.seed_sales` first.

Afterwards, with `GEMINI_API_KEY` set (both skip what is already embedded):

    python -m scripts.rebuild_course_embeddings   # "Khóa học tương tự"
    python -m scripts.ingest_course --all          # the AI assistant
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models import (
    Category,
    Course,
    Enrollment,
    OrderItem,
    Review,
    User,
    VideoAsset,
)
from app.services import certificates
from scripts.seed_courses import (
    KHOA,
    MAI_ANH,
    CourseSpec,
    LessonSpec,
    SectionSpec,
    _build_course,
    sample_hls_url,
    seed_course_id,
)


@dataclass(frozen=True, slots=True)
class CategorySpec:
    name: str
    slug: str
    parent_slug: str | None = None
    """None for a top-level category. A parent named here is either in this
    list (earlier) or one `scripts.seed` writes."""


#: Parents first: a child is written after the parent it points at.
CATEGORIES = [
    CategorySpec("Dữ liệu & Trí tuệ nhân tạo", "du-lieu-tri-tue-nhan-tao"),
    CategorySpec("Khoa học dữ liệu", "khoa-hoc-du-lieu", "du-lieu-tri-tue-nhan-tao"),
    CategorySpec("Học máy & học sâu", "hoc-may", "du-lieu-tri-tue-nhan-tao"),
    CategorySpec("Cơ sở dữ liệu", "co-so-du-lieu"),
    CategorySpec("SQL", "sql", "co-so-du-lieu"),
    CategorySpec("NoSQL", "nosql", "co-so-du-lieu"),
    CategorySpec("DevOps & Đám mây", "devops-dam-may"),
    CategorySpec("Container & Kubernetes", "container-kubernetes", "devops-dam-may"),
    CategorySpec("CI/CD", "ci-cd", "devops-dam-may"),
    CategorySpec("Lập trình di động", "lap-trinh-di-dong"),
    CategorySpec("Flutter", "flutter", "lap-trinh-di-dong"),
    CategorySpec("React Native", "react-native", "lap-trinh-di-dong"),
    CategorySpec("Công cụ lập trình", "cong-cu-lap-trinh"),
    CategorySpec("Git & GitHub", "git-github", "cong-cu-lap-trinh"),
    CategorySpec("Linux & dòng lệnh", "linux-dong-lenh", "cong-cu-lap-trinh"),
    # Children of the trees scripts.seed already writes.
    CategorySpec("Java", "java", "ngon-ngu-lap-trinh"),
    CategorySpec("Go", "golang", "ngon-ngu-lap-trinh"),
    CategorySpec("Bảo mật ứng dụng", "bao-mat-ung-dung", "khoa-hoc-may-tinh"),
]

def _section(title: str, *lessons: tuple[str, int | str]) -> SectionSpec:
    """(title, seconds) is a video, (title, markdown) an article."""
    return SectionSpec(
        title=title,
        lessons=[
            LessonSpec(name, duration_s=body)
            if isinstance(body, int)
            else LessonSpec(name, article=body)
            for name, body in lessons
        ],
    )


def _course(
    slug: str,
    title: str,
    subtitle: str,
    description: str,
    category_slug: str,
    instructor_email: str,
    level: str,
    price: int,
    *sections: SectionSpec,
) -> CourseSpec:
    # The first lesson of a course is its free preview, as in the real seed.
    first = sections[0]
    opened = SectionSpec(
        title=first.title,
        lessons=[
            LessonSpec(
                first.lessons[0].title,
                duration_s=first.lessons[0].duration_s,
                article=first.lessons[0].article,
                preview=True,
            ),
            *first.lessons[1:],
        ],
    )
    return CourseSpec(
        title=title,
        slug=slug,
        subtitle=subtitle,
        description=description,
        category_slug=category_slug,
        instructor_email=instructor_email,
        level=level,
        price=Decimal(price),
        sections=[opened, *sections[1:]],
    )


COURSES: list[CourseSpec] = [
    _course(
        "git-va-github-cho-nguoi-moi",
        "Git và GitHub cho người mới",
        "Lưu lịch sử code, làm việc nhóm và gửi pull request đầu tiên",
        "Git là công cụ mọi lập trình viên dùng hằng ngày nhưng ít ai được dạy bài "
        "bản. Khóa học đi từ commit đầu tiên tới nhánh, gộp nhánh, xử lý xung đột "
        "và quy trình pull request trên GitHub.\n\nMỗi lệnh đều đi kèm câu hỏi "
        "\"lệnh này thay đổi cái gì\" — thư mục làm việc, vùng staging hay lịch sử "
        "— vì hiểu ba vùng đó là hết sợ Git.",
        "git-github", KHOA.email, "beginner", 0,
        _section(
            "Những khái niệm nền tảng",
            ("Git là gì và vì sao cần nó", 402),
            ("Ba vùng của Git: working tree, staging, lịch sử",
             "Mọi lệnh Git đều di chuyển thay đổi giữa **ba vùng**:\n\n"
             "1. **Working tree** — các tệp bạn đang sửa trên đĩa.\n"
             "2. **Staging (index)** — những thay đổi bạn đã chọn cho commit kế tiếp, "
             "bằng `git add`.\n"
             "3. **Lịch sử** — các commit đã ghi, bằng `git commit`.\n\n"
             "`git status` cho biết thay đổi nào đang ở vùng nào. Tập thói quen chạy nó "
             "trước mỗi lệnh khác: phần lớn tình huống \"Git làm mất code của tôi\" là "
             "thay đổi vẫn nằm yên ở working tree mà chưa bao giờ được commit."),
            ("Commit tốt trông như thế nào", 356),
        ),
        _section(
            "Nhánh và làm việc nhóm",
            ("Tạo nhánh và chuyển nhánh", 488),
            ("Merge, rebase và xung đột",
             "Khi hai nhánh cùng sửa một đoạn, Git không tự đoán được bạn muốn giữ bản "
             "nào và dừng lại với **merge conflict**. Tệp bị xung đột chứa cả hai phiên "
             "bản giữa các dấu `<<<<<<<`, `=======` và `>>>>>>>`.\n\n"
             "Cách xử lý: mở tệp, giữ lại đúng đoạn code cuối cùng bạn muốn, xóa các "
             "dấu, rồi `git add` và hoàn tất merge. `rebase` cho lịch sử thẳng hơn nhưng "
             "viết lại commit — **đừng rebase nhánh người khác đã kéo về**."),
            ("Pull request và review code trên GitHub", 534),
        ),
    ),
    _course(
        "dong-lenh-linux-cho-lap-trinh-vien",
        "Dòng lệnh Linux cho lập trình viên",
        "Thao tác tệp, quản lý tiến trình và viết shell script tự động hóa",
        "Máy chủ, container và CI đều chạy Linux, và ở đó không có chuột. Khóa học "
        "dạy những lệnh bạn sẽ gõ hằng ngày: di chuyển trong cây thư mục, tìm và lọc "
        "văn bản, phân quyền, theo dõi tiến trình, rồi ghép chúng thành shell script.",
        "linux-dong-lenh", MAI_ANH.email, "beginner", 199000,
        _section(
            "Làm quen với terminal",
            ("Terminal, shell và dấu nhắc lệnh", 365),
            ("Đường dẫn tuyệt đối và tương đối",
             "Đường dẫn **tuyệt đối** bắt đầu từ gốc `/`, ví dụ `/home/an/du-an`. Đường "
             "dẫn **tương đối** tính từ thư mục hiện tại — `pwd` cho biết bạn đang đứng ở "
             "đâu.\n\n`.` là thư mục hiện tại, `..` là thư mục cha, `~` là thư mục nhà "
             "của bạn. Phím Tab tự hoàn thành tên tệp: dùng nó thay vì gõ tay, vừa nhanh "
             "vừa tránh gõ sai."),
            ("Tạo, chép, di chuyển và xóa tệp", 512),
        ),
        _section(
            "Ống dẫn và tự động hóa",
            ("grep, sort, uniq và ống dẫn |", 476),
            ("Quyền truy cập tệp: rwx và chmod",
             "Mỗi tệp có ba nhóm quyền — chủ sở hữu, nhóm, người khác — mỗi nhóm gồm "
             "đọc (`r`), ghi (`w`), thực thi (`x`). `ls -l` hiện chúng dạng `-rwxr-xr--`.\n\n"
             "`chmod +x deploy.sh` cho phép chạy script. Tránh `chmod 777`: nó cho cả thế "
             "giới quyền ghi, và hầu như không bao giờ là cách sửa đúng cho lỗi "
             "\"Permission denied\"."),
            ("Viết shell script đầu tiên", 598),
        ),
    ),
    _course(
        "sql-tu-co-ban-den-truy-van-phuc-tap",
        "SQL từ cơ bản đến truy vấn phức tạp",
        "SELECT, JOIN, GROUP BY và subquery qua một CSDL bán hàng thật",
        "Học SQL bằng cách trả lời câu hỏi kinh doanh trên một cơ sở dữ liệu cửa hàng: "
        "khách nào mua nhiều nhất, sản phẩm nào bán chạy theo tháng, đơn nào chưa "
        "giao. Từ `SELECT` đơn giản đến `JOIN` nhiều bảng, gộp nhóm và truy vấn lồng.",
        "sql", KHOA.email, "beginner", 249000,
        _section(
            "Truy vấn một bảng",
            ("Cơ sở dữ liệu quan hệ là gì", 344),
            ("SELECT, WHERE và ORDER BY",
             "Một câu truy vấn đọc theo thứ tự: **FROM** bảng nào, **WHERE** lọc dòng "
             "nào, **SELECT** lấy cột nào, **ORDER BY** sắp xếp ra sao.\n\n"
             "```sql\nSELECT ten, gia\nFROM san_pham\nWHERE gia < 500000\n"
             "ORDER BY gia DESC;\n```\n\n"
             "So sánh với `NULL` phải dùng `IS NULL`, không phải `= NULL` — `NULL` "
             "nghĩa là \"không biết\", và so sánh bất cứ thứ gì với nó đều ra không biết."),
            ("LIMIT, DISTINCT và bí danh cột", 298),
        ),
        _section(
            "Nhiều bảng và gộp nhóm",
            ("INNER JOIN và LEFT JOIN", 566),
            ("GROUP BY và HAVING",
             "`GROUP BY` gom các dòng cùng giá trị thành một nhóm để tính `COUNT`, "
             "`SUM`, `AVG`. `WHERE` lọc **trước** khi gom, `HAVING` lọc **sau** khi gom:\n\n"
             "```sql\nSELECT khach_hang_id, SUM(tong_tien) AS doanh_thu\nFROM don_hang\n"
             "WHERE trang_thai = 'da_giao'\nGROUP BY khach_hang_id\n"
             "HAVING SUM(tong_tien) > 10000000;\n```"),
            ("Subquery và CTE với WITH", 487),
        ),
    ),
    _course(
        "thiet-ke-co-so-du-lieu-quan-he",
        "Thiết kế cơ sở dữ liệu quan hệ",
        "Mô hình hóa nghiệp vụ, chuẩn hóa và chọn khóa, chỉ mục cho đúng",
        "Một lược đồ tồi làm mọi tính năng sau đó khó viết và chậm chạy. Khóa học dạy "
        "cách đi từ yêu cầu nghiệp vụ tới sơ đồ thực thể – quan hệ, chuẩn hóa tới 3NF, "
        "chọn khóa chính, khóa ngoại, ràng buộc và chỉ mục — và biết khi nào nên "
        "phi chuẩn hóa.",
        "sql", MAI_ANH.email, "intermediate", 349000,
        _section(
            "Từ nghiệp vụ tới lược đồ",
            ("Thực thể, thuộc tính và quan hệ", 455),
            ("Quan hệ một – nhiều và nhiều – nhiều",
             "Quan hệ **một – nhiều** (một khách hàng có nhiều đơn hàng) biểu diễn bằng "
             "khóa ngoại ở phía \"nhiều\": bảng `don_hang` có cột `khach_hang_id`.\n\n"
             "Quan hệ **nhiều – nhiều** (một học viên học nhiều khóa, một khóa có nhiều "
             "học viên) cần **bảng trung gian** chứa hai khóa ngoại, kèm ràng buộc "
             "`UNIQUE` trên cặp đó. Bảng trung gian thường có dữ liệu của riêng nó — "
             "ngày ghi danh, tiến độ — và đó là dấu hiệu bạn đã mô hình đúng."),
        ),
        _section(
            "Chuẩn hóa và hiệu năng",
            ("1NF, 2NF, 3NF qua ví dụ", 612),
            ("Chỉ mục: khi nào giúp, khi nào hại",
             "Chỉ mục B-tree giúp tìm nhanh theo cột được đánh chỉ mục, nhưng mỗi lần "
             "`INSERT`/`UPDATE` phải cập nhật thêm nó. Đánh chỉ mục cho cột xuất hiện "
             "trong `WHERE`, `JOIN` và `ORDER BY` của truy vấn chạy thường xuyên — "
             "không phải cho mọi cột.\n\nDùng `EXPLAIN ANALYZE` để xem truy vấn có thật "
             "sự dùng chỉ mục không, thay vì đoán."),
            ("Ràng buộc CHECK, UNIQUE và khóa ngoại", 421),
        ),
    ),
    _course(
        "mongodb-cho-ung-dung-web",
        "MongoDB cho ứng dụng web",
        "Thiết kế document, truy vấn, aggregation pipeline và chỉ mục",
        "MongoDB lưu dữ liệu dạng document JSON linh hoạt, nhưng linh hoạt không có "
        "nghĩa là không cần thiết kế. Khóa học dạy khi nào nhúng, khi nào tham chiếu, "
        "cách viết truy vấn và aggregation pipeline, và cách đánh chỉ mục cho tải "
        "đọc thật của ứng dụng.",
        "nosql", KHOA.email, "intermediate", 299000,
        _section(
            "Document và collection",
            ("SQL và NoSQL khác nhau ở đâu", 389),
            ("Nhúng hay tham chiếu",
             "Quy tắc chung: **dữ liệu được đọc cùng nhau thì lưu cùng nhau**. Địa chỉ "
             "giao hàng của một đơn nên nhúng vào document đơn hàng; danh sách bình "
             "luận có thể tăng không giới hạn của một bài viết thì nên tách collection "
             "riêng và tham chiếu.\n\nGiới hạn 16 MB mỗi document là lời nhắc rằng mảng "
             "lớn dần mãi mãi không thuộc về một document."),
            ("CRUD với MongoDB Shell", 467),
        ),
        _section(
            "Truy vấn nâng cao",
            ("Aggregation pipeline: $match, $group, $lookup", 573),
            ("Chỉ mục và explain()",
             "Không có chỉ mục, MongoDB phải quét toàn bộ collection (`COLLSCAN`). "
             "`db.orders.find({...}).explain(\"executionStats\")` cho biết số document "
             "đã xem so với số trả về — chênh lệch lớn là dấu hiệu thiếu chỉ mục.\n\n"
             "Với chỉ mục ghép, thứ tự trường quan trọng: trường lọc bằng giá trị cụ thể "
             "đứng trước, trường sắp xếp và lọc theo khoảng đứng sau."),
        ),
    ),
    _course(
        "thong-ke-ung-dung-cho-khoa-hoc-du-lieu",
        "Thống kê ứng dụng cho khoa học dữ liệu",
        "Trung bình, phân phối, kiểm định giả thuyết — giải thích bằng ví dụ, không bằng công thức",
        "Khoa học dữ liệu bắt đầu từ thống kê. Khóa học giải thích các khái niệm cốt "
        "lõi — trung bình và trung vị, độ lệch chuẩn, phân phối chuẩn, khoảng tin cậy, "
        "kiểm định A/B — bằng dữ liệu thật và trực giác, rồi mới tới công thức.",
        "khoa-hoc-du-lieu", MAI_ANH.email, "beginner", 0,
        _section(
            "Mô tả dữ liệu",
            ("Vì sao lập trình viên cần thống kê", 312),
            ("Trung bình hay trung vị",
             "Trung bình bị kéo mạnh bởi giá trị ngoại lai. Lương của mười người, chín "
             "người 10 triệu và một người 200 triệu: trung bình là 29 triệu — không ai "
             "trong nhóm có mức lương đó. Trung vị là 10 triệu, sát với thực tế hơn.\n\n"
             "Khi dữ liệu lệch (thu nhập, thời gian phản hồi của máy chủ, giá nhà), "
             "báo cáo trung vị và các phân vị như p95 thay vì chỉ trung bình."),
            ("Phương sai và độ lệch chuẩn", 405),
        ),
        _section(
            "Suy luận từ mẫu",
            ("Phân phối chuẩn và định lý giới hạn trung tâm", 534),
            ("Kiểm định A/B và p-value",
             "Kiểm định A/B so sánh hai phiên bản, ví dụ hai màu nút \"Mua ngay\". "
             "**p-value** là xác suất thấy khác biệt lớn như vậy *nếu thật ra hai phiên "
             "bản như nhau*. p-value nhỏ (thường < 0,05) gợi ý khác biệt không do may "
             "rủi.\n\np-value **không** phải xác suất phiên bản B tốt hơn, và cũng không "
             "nói khác biệt lớn hay nhỏ. Luôn báo kèm kích thước hiệu ứng."),
        ),
    ),
    _course(
        "hoc-sau-voi-pytorch-tu-dau",
        "Học sâu với PyTorch từ đầu",
        "Tensor, autograd, mạng nơ-ron tích chập và huấn luyện trên GPU",
        "Khóa học dựng mạng nơ-ron từ những viên gạch nhỏ nhất: tensor, đạo hàm tự "
        "động, vòng lặp huấn luyện viết tay — trước khi dùng `nn.Module` và "
        "`DataLoader`. Kết thúc bằng một mạng tích chập phân loại ảnh và các kỹ thuật "
        "chống overfitting.\n\nCần biết Python và đại số tuyến tính cơ bản.",
        "hoc-may", KHOA.email, "advanced", 799000,
        _section(
            "Nền tảng",
            ("Tensor và phép toán trên GPU", 547),
            ("Autograd: đạo hàm tự động hoạt động thế nào",
             "Mỗi phép toán trên tensor có `requires_grad=True` được ghi vào một **đồ "
             "thị tính toán**. Gọi `loss.backward()` đi ngược đồ thị đó theo quy tắc "
             "chuỗi và cộng dồn đạo hàm vào `.grad` của từng tham số.\n\n"
             "\"Cộng dồn\" là chỗ người mới hay vấp: nếu quên `optimizer.zero_grad()` "
             "trước mỗi bước, đạo hàm của các batch trước cộng vào batch này và mô hình "
             "học sai mà không báo lỗi gì."),
            ("Vòng lặp huấn luyện viết tay", 633),
        ),
        _section(
            "Mạng tích chập",
            ("Convolution, pooling và feature map", 588),
            ("Overfitting: dropout, augmentation và early stopping",
             "Mô hình overfit khi loss trên tập huấn luyện tiếp tục giảm còn loss trên "
             "tập kiểm định bắt đầu tăng: nó đang học thuộc dữ liệu thay vì học quy "
             "luật.\n\nBa cách chống phổ biến: **dropout** tắt ngẫu nhiên một phần nơ-ron "
             "khi huấn luyện; **data augmentation** lật, cắt, đổi màu ảnh để tạo thêm dữ "
             "liệu; **early stopping** dừng khi loss kiểm định không cải thiện sau vài "
             "epoch và giữ trọng số tốt nhất."),
        ),
        _section(
            "Đưa mô hình ra dùng",
            ("Lưu, nạp và suy luận với mô hình đã huấn luyện", 402),
        ),
    ),
    _course(
        "xu-ly-ngon-ngu-tu-nhien-tieng-viet",
        "Xử lý ngôn ngữ tự nhiên cho tiếng Việt",
        "Tách từ, biểu diễn văn bản, phân loại cảm xúc và tìm kiếm ngữ nghĩa",
        "Tiếng Việt có những khó khăn riêng: từ ghép nhiều âm tiết, dấu thanh, văn bản "
        "mạng không dấu. Khóa học đi qua tách từ, TF-IDF, word embedding, mô hình "
        "Transformer tiền huấn luyện, rồi xây bộ phân loại cảm xúc bình luận và một "
        "công cụ tìm kiếm ngữ nghĩa.",
        "hoc-may", MAI_ANH.email, "advanced", 699000,
        _section(
            "Tiền xử lý văn bản",
            ("Vì sao tiếng Việt khó với máy", 421),
            ("Tách từ và chuẩn hóa Unicode",
             "\"Học sinh\" là **một từ** gồm hai âm tiết, nên tách theo dấu cách cho kết "
             "quả sai. Bộ tách từ tiếng Việt nối âm tiết thành `học_sinh` trước khi đưa "
             "vào mô hình.\n\nMột bẫy khác: chữ \"ệ\" có thể được lưu bằng một ký tự hoặc "
             "bằng \"e\" cộng hai dấu kết hợp. Trông giống hệt nhưng so sánh chuỗi ra "
             "khác. Chuẩn hóa về **NFC** (`unicodedata.normalize(\"NFC\", s)`) trước mọi "
             "bước khác."),
        ),
        _section(
            "Biểu diễn và mô hình",
            ("TF-IDF và túi từ", 476),
            ("Embedding và tìm kiếm ngữ nghĩa",
             "Embedding biến một câu thành một vector sao cho câu cùng nghĩa nằm gần "
             "nhau. \"Cách đổi mật khẩu\" và \"quên mật khẩu thì làm sao\" không chung "
             "nhiều từ nhưng có vector gần nhau, nên tìm kiếm ngữ nghĩa thấy được thứ "
             "tìm kiếm theo từ khóa bỏ sót.\n\nĐộ gần thường đo bằng **cosine "
             "similarity**. Lưu vector trong CSDL có chỉ mục ANN (như pgvector với HNSW) "
             "để tìm nhanh trên hàng triệu câu."),
            ("Tinh chỉnh mô hình Transformer cho phân loại cảm xúc", 702),
        ),
    ),
    _course(
        "kubernetes-trien-khai-ung-dung-that",
        "Kubernetes: triển khai ứng dụng thật",
        "Pod, Deployment, Service, Ingress, ConfigMap và tự co giãn",
        "Khóa học đưa một ứng dụng web gồm frontend, API và CSDL lên Kubernetes từng "
        "bước: đóng gói, viết manifest, mở ra ngoài bằng Ingress, quản lý cấu hình và "
        "bí mật, cập nhật không gián đoạn và tự co giãn theo tải.\n\nCần đã quen "
        "Docker.",
        "container-kubernetes", KHOA.email, "advanced", 649000,
        _section(
            "Các khối cơ bản",
            ("Kubernetes giải quyết vấn đề gì", 433),
            ("Pod, ReplicaSet và Deployment",
             "**Pod** là đơn vị nhỏ nhất Kubernetes chạy — một hoặc vài container chung "
             "mạng và ổ đĩa. Pod có thể chết bất cứ lúc nào và không tự sống lại.\n\n"
             "Vì vậy ta hầu như không tạo Pod trực tiếp mà khai báo một **Deployment**: "
             "\"tôi muốn 3 bản của image này\". Deployment tạo ReplicaSet, ReplicaSet giữ "
             "đúng 3 Pod chạy, và khi đổi image thì Deployment thay Pod dần dần — đó là "
             "rolling update."),
            ("Service và Ingress: đưa ứng dụng ra ngoài", 567),
        ),
        _section(
            "Vận hành",
            ("ConfigMap, Secret và biến môi trường", 412),
            ("Liveness, readiness và tự co giãn",
             "**Readiness probe** trả lời \"Pod này nhận request được chưa\" — chưa thì "
             "Service không gửi tải vào. **Liveness probe** trả lời \"Pod này còn sống "
             "không\" — không thì Kubernetes khởi động lại nó.\n\nĐừng để liveness phụ "
             "thuộc CSDL: CSDL chậm một lúc là mọi Pod API bị khởi động lại cùng lúc, "
             "biến sự cố nhỏ thành sập toàn bộ."),
        ),
    ),
    _course(
        "ci-cd-voi-github-actions",
        "CI/CD với GitHub Actions",
        "Tự động chạy test, build image và triển khai mỗi lần push",
        "Mỗi lần push, máy tự chạy lint và test; mỗi lần merge vào nhánh chính, máy "
        "tự build và triển khai. Khóa học dựng một pipeline như vậy bằng GitHub "
        "Actions: workflow, job, cache, ma trận phiên bản, bí mật và môi trường.",
        "ci-cd", MAI_ANH.email, "intermediate", 0,
        _section(
            "Tích hợp liên tục",
            ("CI/CD là gì và lợi ích thật", 351),
            ("Workflow, job và step",
             "Một **workflow** là tệp YAML trong `.github/workflows/`, chạy khi có sự "
             "kiện như `push` hoặc `pull_request`. Workflow gồm các **job** chạy song "
             "song trên máy ảo riêng; mỗi job là chuỗi **step** chạy tuần tự.\n\n"
             "Các job không chung ổ đĩa. Muốn job sau dùng kết quả build của job trước, "
             "khai báo `needs:` và truyền tệp qua artifact."),
            ("Cache dependency để pipeline nhanh hơn", 398),
        ),
        _section(
            "Triển khai liên tục",
            ("Build và đẩy Docker image", 476),
            ("Bí mật và môi trường triển khai",
             "Mật khẩu, token triển khai lưu ở **Secrets** của repo hoặc của environment, "
             "đọc qua `${{ secrets.TEN }}`, và được che trong log.\n\nGắn job triển khai "
             "vào một **environment** như `production` để bắt buộc người duyệt trước khi "
             "chạy, và để bí mật production không lọt vào workflow của pull request từ "
             "fork."),
        ),
    ),
    _course(
        "flutter-xay-dung-ung-dung-di-dong-dau-tien",
        "Flutter: xây dựng ứng dụng di động đầu tiên",
        "Một mã nguồn cho cả Android và iOS, từ widget tới gọi API",
        "Khóa học dựng một ứng dụng ghi chú hoàn chỉnh bằng Flutter: bố cục bằng "
        "widget, điều hướng giữa các màn, quản lý trạng thái, gọi REST API và lưu dữ "
        "liệu trên máy. Không cần biết Dart trước — chương đầu dạy đủ dùng.",
        "flutter", KHOA.email, "beginner", 399000,
        _section(
            "Dart và widget",
            ("Cài Flutter và chạy ứng dụng mẫu", 487),
            ("Mọi thứ đều là widget",
             "Trong Flutter, nút bấm, chữ, khoảng cách, cả bố cục hàng và cột đều là "
             "**widget** lồng vào nhau thành cây. `StatelessWidget` chỉ vẽ theo dữ liệu "
             "được truyền vào; `StatefulWidget` giữ trạng thái riêng và vẽ lại khi gọi "
             "`setState`.\n\nMẹo đầu tiên: tách widget lớn thành widget nhỏ có tên. Cây "
             "dễ đọc hơn, và Flutter chỉ dựng lại phần thật sự thay đổi."),
            ("Row, Column, Stack và bố cục đáp ứng", 545),
        ),
        _section(
            "Ứng dụng hoàn chỉnh",
            ("Điều hướng giữa các màn hình", 402),
            ("Gọi API và hiển thị trạng thái tải",
             "Gọi mạng luôn có ba trạng thái: **đang tải**, **thành công**, **lỗi**. "
             "`FutureBuilder` vẽ theo từng trạng thái của một `Future`.\n\nĐừng tạo "
             "`Future` ngay trong `build()`: mỗi lần vẽ lại sẽ gọi API lần nữa. Tạo nó một "
             "lần trong `initState` rồi truyền vào `FutureBuilder`."),
            ("Lưu dữ liệu cục bộ", 433),
        ),
    ),
    _course(
        "react-native-tu-web-sang-di-dong",
        "React Native: từ web sang di động",
        "Dùng kiến thức React sẵn có để làm ứng dụng iOS và Android",
        "Bạn đã viết React cho web? Khóa học chỉ ra những gì giữ nguyên — component, "
        "props, state, hook — và những gì khác: không có DOM, không có CSS, điều hướng "
        "theo ngăn xếp, quyền truy cập thiết bị. Thực hành bằng Expo, chạy thẳng trên "
        "điện thoại.",
        "react-native", MAI_ANH.email, "intermediate", 449000,
        _section(
            "Khác biệt với React web",
            ("Expo và môi trường phát triển", 376),
            ("View, Text và StyleSheet thay cho div và CSS",
             "React Native không có `div` hay `span`: bố cục dùng `View`, chữ **bắt "
             "buộc** nằm trong `Text`. Kiểu dáng viết bằng object JavaScript qua "
             "`StyleSheet.create`, không có cascade — kiểu chữ không tự kế thừa từ "
             "`View` cha.\n\nFlexbox là mặc định và hướng chính là **cột**, ngược với web. "
             "Nhớ điều này là đỡ được nửa số bố cục bị lệch."),
        ),
        _section(
            "Ứng dụng thật",
            ("Điều hướng với React Navigation", 512),
            ("FlatList cho danh sách dài",
             "`map` qua một mảng 5.000 phần tử và vẽ tất cả sẽ làm ứng dụng giật. "
             "`FlatList` chỉ vẽ những dòng đang nằm trên màn hình cộng một ít phía "
             "trước, và tái sử dụng chúng khi cuộn.\n\nLuôn truyền `keyExtractor` trả về "
             "khóa ổn định, và giữ component của từng dòng nhẹ — dùng `React.memo` khi "
             "dòng phức tạp."),
            ("Camera, vị trí và quyền truy cập", 467),
        ),
    ),
    _course(
        "java-co-ban-va-lap-trinh-huong-doi-tuong",
        "Java cơ bản và lập trình hướng đối tượng",
        "Cú pháp Java, lớp và đối tượng, kế thừa, interface và collection",
        "Java vẫn là ngôn ngữ của rất nhiều hệ thống doanh nghiệp, ngân hàng và ứng "
        "dụng Android. Khóa học dạy cú pháp từ đầu, rồi tập trung vào lập trình hướng "
        "đối tượng: đóng gói, kế thừa, đa hình, interface — kèm Collections Framework "
        "và xử lý ngoại lệ.",
        "java", KHOA.email, "beginner", 299000,
        _section(
            "Cú pháp Java",
            ("JDK, JVM và chương trình đầu tiên", 423),
            ("Kiểu nguyên thủy và kiểu tham chiếu",
             "`int`, `double`, `boolean` là kiểu **nguyên thủy**: biến chứa chính giá "
             "trị. `String`, mảng và mọi đối tượng là kiểu **tham chiếu**: biến chứa địa "
             "chỉ tới đối tượng.\n\nVì vậy `a == b` với hai `String` so sánh *địa chỉ*, "
             "không phải nội dung — hai chuỗi giống hệt vẫn có thể ra `false`. So sánh "
             "nội dung chuỗi luôn dùng `a.equals(b)`."),
            ("Vòng lặp, mảng và phương thức", 498),
        ),
        _section(
            "Hướng đối tượng",
            ("Lớp, đối tượng và hàm khởi tạo", 532),
            ("Kế thừa hay interface",
             "Kế thừa (`extends`) diễn tả quan hệ **\"là một\"**: `HinhTron` là một "
             "`Hinh`. Java chỉ cho kế thừa một lớp. **Interface** (`implements`) diễn tả "
             "**\"làm được\"**: một lớp có thể `Comparable`, `Serializable` cùng lúc.\n\n"
             "Khi phân vân, ưu tiên interface và composition — kế thừa sâu nhiều tầng "
             "khiến sửa lớp cha là làm vỡ lớp con ở chỗ không ngờ."),
            ("ArrayList, HashMap và xử lý ngoại lệ", 556),
        ),
    ),
    _course(
        "spring-boot-xay-dung-dich-vu-backend",
        "Spring Boot: xây dựng dịch vụ backend",
        "REST API, Spring Data JPA, xác thực JWT và kiểm thử",
        "Khóa học xây một API quản lý thư viện bằng Spring Boot: controller, service, "
        "repository với Spring Data JPA, kiểm tra dữ liệu đầu vào, xử lý lỗi tập "
        "trung, bảo vệ bằng Spring Security + JWT và viết test tích hợp.",
        "backend", MAI_ANH.email, "intermediate", 549000,
        _section(
            "Nền tảng Spring",
            ("Spring Boot và dependency injection", 476),
            ("Controller, service, repository: mỗi lớp một việc",
             "**Controller** nhận request và trả response — không chứa nghiệp vụ. "
             "**Service** chứa nghiệp vụ và ranh giới transaction (`@Transactional`). "
             "**Repository** nói chuyện với CSDL.\n\nGiữ đúng ranh giới này thì test "
             "service không cần dựng HTTP, và đổi cách lưu trữ không phải sửa controller. "
             "Dấu hiệu sai: controller gọi thẳng repository rồi tự tính toán."),
            ("Spring Data JPA và quan hệ giữa entity", 589),
        ),
        _section(
            "Sẵn sàng cho production",
            ("Validation và xử lý lỗi với @ControllerAdvice", 432),
            ("Bảo mật API bằng JWT",
             "Sau khi đăng nhập, máy chủ cấp một **access token** JWT ngắn hạn; client "
             "gửi nó trong header `Authorization: Bearer ...`. Một filter của Spring "
             "Security kiểm chữ ký và hạn của token trước khi request vào controller.\n\n"
             "JWT ký chứ không mã hóa: ai cũng đọc được nội dung, nên **đừng đặt dữ liệu "
             "nhạy cảm** vào đó. Giữ access token ngắn hạn và dùng refresh token để gia "
             "hạn."),
        ),
    ),
    _course(
        "go-cho-lap-trinh-vien-backend",
        "Go cho lập trình viên backend",
        "Cú pháp gọn, goroutine, channel và dịch vụ HTTP hiệu năng cao",
        "Go được thiết kế cho dịch vụ mạng: biên dịch nhanh, một tệp thực thi, chạy "
        "đồng thời rẻ. Khóa học dành cho người đã biết một ngôn ngữ khác, đi nhanh qua "
        "cú pháp rồi tập trung vào interface, xử lý lỗi kiểu Go, goroutine, channel "
        "và viết một dịch vụ HTTP hoàn chỉnh.",
        "golang", KHOA.email, "intermediate", 499000,
        _section(
            "Ngôn ngữ Go",
            ("Vì sao chọn Go", 334),
            ("Xử lý lỗi: if err != nil",
             "Go không có ngoại lệ. Hàm có thể hỏng trả về thêm một giá trị `error`, và "
             "người gọi kiểm nó ngay:\n\n```go\nf, err := os.Open(path)\nif err != nil {\n"
             "    return fmt.Errorf(\"mở cấu hình: %w\", err)\n}\n```\n\n"
             "Bọc lỗi bằng `%w` giữ lại lỗi gốc để `errors.Is` vẫn nhận ra, đồng thời "
             "thêm ngữ cảnh — log cuối cùng đọc như một câu chuyện thay vì chỉ "
             "\"file not found\"."),
            ("Struct, method và interface ngầm định", 512),
        ),
        _section(
            "Đồng thời",
            ("Goroutine và channel", 567),
            ("context: hủy và giới hạn thời gian",
             "Một request HTTP bị client hủy thì mọi goroutine làm việc cho nó nên dừng "
             "theo. `context.Context` mang tín hiệu hủy và hạn chót đi xuyên qua các lời "
             "gọi.\n\nQuy ước: `ctx` là tham số đầu tiên của hàm làm I/O, và không lưu "
             "context trong struct. Dùng `context.WithTimeout` khi gọi dịch vụ ngoài để "
             "một dịch vụ chậm không kéo cả hệ thống chậm theo."),
            ("Viết dịch vụ HTTP với net/http", 498),
        ),
    ),
    _course(
        "nodejs-va-express-xay-dung-api",
        "Node.js và Express: xây dựng API",
        "Từ server đầu tiên tới API có xác thực, kết nối CSDL và xử lý lỗi",
        "Khóa học nhập môn backend bằng JavaScript: hiểu event loop của Node.js, dựng "
        "server với Express, tổ chức route và middleware, kết nối PostgreSQL, xác thực "
        "người dùng và xử lý lỗi đúng cách. Phù hợp cho người đã biết JavaScript cơ "
        "bản.",
        "backend", MAI_ANH.email, "beginner", 0,
        _section(
            "Node.js",
            ("Node.js chạy JavaScript ngoài trình duyệt", 356),
            ("Event loop và I/O không chặn",
             "Node.js chạy JavaScript trên **một luồng**. Khi đọc tệp hay gọi CSDL, nó "
             "không ngồi chờ mà đăng ký callback rồi xử lý request khác; khi I/O xong, "
             "event loop gọi callback đó.\n\nHệ quả: một vòng lặp tính toán nặng làm "
             "**mọi** request khác đứng chờ. Việc nặng CPU nên đẩy sang worker thread "
             "hoặc hàng đợi riêng."),
        ),
        _section(
            "Express",
            ("Route, request và response", 445),
            ("Middleware và xử lý lỗi tập trung",
             "Middleware là hàm `(req, res, next)` chạy theo thứ tự khai báo: ghi log, "
             "đọc JSON, kiểm tra đăng nhập... Gọi `next()` để chuyển tiếp, gọi "
             "`next(err)` để nhảy thẳng tới middleware xử lý lỗi — hàm có **bốn** tham "
             "số `(err, req, res, next)`.\n\nGom mọi lỗi về một chỗ đó để định dạng phản "
             "hồi thống nhất và không bao giờ lộ stack trace cho người dùng."),
            ("Kết nối PostgreSQL và xác thực người dùng", 578),
        ),
    ),
    _course(
        "javascript-bat-dong-bo-promise-async-await",
        "JavaScript bất đồng bộ: Promise và async/await",
        "Hiểu callback, Promise, async/await và event loop để hết sợ code bất đồng bộ",
        "Gọi API, đọc tệp, hẹn giờ — JavaScript làm mọi thứ bất đồng bộ, và lỗi khó "
        "nhất thường nằm ở đó. Khóa học đi từ callback tới Promise và async/await, giải "
        "thích event loop, cách chạy song song đúng và cách bắt lỗi không bị nuốt mất.",
        "javascript", KHOA.email, "intermediate", 149000,
        _section(
            "Từ callback tới Promise",
            ("Vì sao JavaScript bất đồng bộ", 312),
            ("Promise: ba trạng thái",
             "Một Promise ở một trong ba trạng thái: **pending** (đang chờ), "
             "**fulfilled** (xong, có giá trị), **rejected** (hỏng, có lỗi). Đã ra "
             "fulfilled hoặc rejected thì không đổi nữa.\n\n`.then()` luôn trả về một "
             "Promise **mới**, nên có thể nối chuỗi. Quên `return` trong `.then()` là lỗi "
             "kinh điển: bước sau chạy ngay mà không chờ bước trước."),
        ),
        _section(
            "async/await trong thực tế",
            ("async/await và try/catch", 398),
            ("Chạy song song với Promise.all",
             "`await` lần lượt ba lời gọi độc lập thì tổng thời gian là tổng ba lần chờ:\n\n"
             "```js\nconst [user, posts, stats] = await Promise.all([\n"
             "  getUser(id), getPosts(id), getStats(id),\n]);\n```\n\n"
             "`Promise.all` chạy cả ba cùng lúc và hỏng ngay khi một cái hỏng. Muốn lấy "
             "kết quả của những cái thành công dù có cái hỏng, dùng "
             "`Promise.allSettled`."),
            ("Event loop: microtask và macrotask", 476),
        ),
    ),
    _course(
        "vue-3-composition-api",
        "Vue 3 và Composition API",
        "Xây giao diện phản ứng với ref, computed, composable và Pinia",
        "Vue 3 nhẹ, dễ học và rất phổ biến trong các dự án tại Việt Nam. Khóa học dạy "
        "Composition API từ đầu: hệ thống phản ứng, component và props, tách logic "
        "thành composable, điều hướng với Vue Router và quản lý trạng thái chung bằng "
        "Pinia.",
        "frontend", MAI_ANH.email, "intermediate", 349000,
        _section(
            "Hệ thống phản ứng",
            ("Ứng dụng Vue đầu tiên với Vite", 365),
            ("ref, reactive và computed",
             "`ref(0)` bọc một giá trị để Vue theo dõi thay đổi; trong script đọc ghi "
             "qua `.value`, trong template thì không cần. `reactive({...})` làm cả "
             "object phản ứng nhưng mất tính phản ứng nếu bị destructure.\n\n"
             "`computed` tính giá trị dẫn xuất và **tự nhớ** kết quả cho tới khi phụ "
             "thuộc đổi. Đừng dùng `watch` để đồng bộ một biến từ biến khác — đó là việc "
             "của `computed`."),
        ),
        _section(
            "Ứng dụng nhiều trang",
            ("Component, props và emit", 456),
            ("Composable: tái sử dụng logic",
             "Composable là hàm bắt đầu bằng `use`, gói một mẩu logic có trạng thái để "
             "nhiều component dùng chung — ví dụ `useFetch(url)` trả về `data`, `error`, "
             "`loading`.\n\nKhác mixin của Vue 2, nguồn gốc của mỗi biến hiện rõ ở dòng "
             "gọi composable, và hai composable không âm thầm ghi đè tên của nhau."),
            ("Vue Router và Pinia", 534),
        ),
    ),
    _course(
        "bao-mat-ung-dung-web-owasp-top-10",
        "Bảo mật ứng dụng web: OWASP Top 10",
        "Hiểu và phòng chống SQL injection, XSS, CSRF và lỗi phân quyền",
        "Phần lớn lỗ hổng web lặp lại cùng vài kiểu. Khóa học đi qua OWASP Top 10 "
        "theo cách của người viết code: mỗi lỗ hổng có một ví dụ code lỗi, cách tấn "
        "công nó trong môi trường thử nghiệm, và cách sửa đúng ở tầng ứng dụng.",
        "bao-mat-ung-dung", KHOA.email, "intermediate", 449000,
        _section(
            "Tấn công vào dữ liệu đầu vào",
            ("Tư duy của người tấn công", 389),
            ("SQL injection và truy vấn tham số hóa",
             "Ghép chuỗi người dùng nhập vào câu SQL là trao cho họ quyền viết SQL:\n\n"
             "```python\n# Sai\ncur.execute(f\"SELECT * FROM users WHERE email = '{email}'\")\n"
             "# Đúng\ncur.execute(\"SELECT * FROM users WHERE email = %s\", (email,))\n```\n\n"
             "Với truy vấn tham số hóa, dữ liệu không bao giờ được hiểu là lệnh. Lọc ký "
             "tự đặc biệt bằng tay **không** phải cách phòng chống — luôn có cách vòng "
             "qua."),
            ("Cross-site scripting (XSS) và Content Security Policy", 512),
        ),
        _section(
            "Xác thực và phân quyền",
            ("CSRF và cookie SameSite", 423),
            ("Lỗi phân quyền: IDOR",
             "`GET /orders/1042` trả đơn hàng 1042 — nhưng có phải đơn **của người đang "
             "hỏi** không? Quên kiểm tra quyền sở hữu là lỗ hổng IDOR, đứng đầu OWASP Top "
             "10 nhiều năm liền.\n\nĐăng nhập (xác thực) chưa đủ: mọi endpoint đọc hay sửa "
             "một tài nguyên theo id phải kiểm người hỏi có quyền với **đúng tài nguyên "
             "đó**. Trả 404 thay vì 403 để không xác nhận id tồn tại."),
        ),
    ),
    _course(
        "thiet-ke-huong-doi-tuong-va-solid-trong-python",
        "Thiết kế hướng đối tượng và SOLID trong Python",
        "Lớp, kế thừa, dunder method, dataclass và năm nguyên lý SOLID",
        "Bước tiếp theo sau Python cơ bản: tổ chức chương trình bằng lớp và đối "
        "tượng. Khóa học dạy cách định nghĩa lớp, kế thừa và đa hình, các dunder "
        "method làm đối tượng của bạn hành xử như kiểu có sẵn, `dataclass`, và các "
        "nguyên lý SOLID qua bài tập thiết kế nhỏ.",
        "python", MAI_ANH.email, "intermediate", 199000,
        _section(
            "Lớp và đối tượng",
            ("Vì sao cần hướng đối tượng", 334),
            ("self, thuộc tính và phương thức",
             "`self` là đối tượng đang gọi phương thức — Python truyền nó vào tự động: "
             "`tk.nap_tien(100)` thực chất là `TaiKhoan.nap_tien(tk, 100)`.\n\n"
             "Thuộc tính gán trong `__init__` thuộc về **từng đối tượng**; thuộc tính "
             "khai báo ngay trong thân lớp thuộc về **lớp**, dùng chung. Đặt một list làm "
             "thuộc tính lớp rồi `append` từ một đối tượng là mọi đối tượng cùng thấy "
             "thay đổi."),
            ("Kế thừa, super() và đa hình", 487),
        ),
        _section(
            "Python hơn nữa",
            ("Dunder method: __str__, __eq__, __len__", 412),
            ("dataclass thay cho lớp viết tay",
             "Lớp chỉ để chứa dữ liệu thường lặp lại `__init__`, `__repr__`, `__eq__`. "
             "`@dataclass` sinh chúng từ khai báo kiểu:\n\n"
             "```python\nfrom dataclasses import dataclass\n\n@dataclass(frozen=True)\n"
             "class Diem:\n    x: float\n    y: float\n```\n\n"
             "`frozen=True` làm đối tượng bất biến và dùng được làm khóa của `dict`."),
        ),
    ),
    _course(
        "thuat-toan-sap-xep-va-tim-kiem",
        "Thuật toán sắp xếp và tìm kiếm",
        "Từ sắp xếp nổi bọt tới quicksort, merge sort và tìm kiếm nhị phân",
        "Sắp xếp và tìm kiếm là cửa vào của môn giải thuật. Khóa học cài đặt từng thuật "
        "toán bằng Python, mô phỏng từng bước, so sánh độ phức tạp và chỉ ra khi nào "
        "nên dùng cái nào — kèm những biến thể tìm kiếm nhị phân hay gặp trong phỏng "
        "vấn.",
        "cau-truc-du-lieu-giai-thuat", KHOA.email, "beginner", 0,
        _section(
            "Sắp xếp",
            ("Sắp xếp nổi bọt, chọn và chèn", 456),
            ("Merge sort và quicksort",
             "**Merge sort** chia đôi mảng, sắp xếp từng nửa, rồi trộn hai nửa đã sắp: "
             "luôn O(n log n) nhưng cần thêm bộ nhớ. **Quicksort** chọn một chốt, dồn "
             "phần nhỏ hơn sang trái, lớn hơn sang phải, rồi đệ quy: trung bình O(n log "
             "n), tệ nhất O(n²) khi chốt chọn kém.\n\n`sorted()` của Python dùng "
             "Timsort — lai giữa merge sort và insertion sort, ổn định và rất nhanh với "
             "dữ liệu đã gần sắp xếp."),
        ),
        _section(
            "Tìm kiếm",
            ("Tìm kiếm tuần tự và nhị phân", 398),
            ("Tìm kiếm nhị phân trên đáp án",
             "Tìm kiếm nhị phân không chỉ dùng trên mảng. Khi câu hỏi có dạng \"giá trị "
             "nhỏ nhất thỏa điều kiện\" và điều kiện **đơn điệu** (đúng với x thì đúng "
             "với mọi số lớn hơn), ta tìm nhị phân trên chính đáp án.\n\nVí dụ: tốc độ "
             "nhỏ nhất để đọc xong sách trong H giờ. Thử tốc độ ở giữa khoảng, đọc kịp "
             "thì thu nửa trên, không kịp thì thu nửa dưới."),
            ("Bài tập: các biến thể lower_bound và upper_bound", 445),
        ),
    ),
    _course(
        "kien-truc-microservices-thuc-chien",
        "Kiến trúc microservices thực chiến",
        "Tách dịch vụ, giao tiếp bất đồng bộ, dữ liệu phân tán và quan sát hệ thống",
        "Microservices giải quyết bài toán tổ chức của đội lớn, đổi lại bằng độ phức "
        "tạp phân tán. Khóa học dạy khi nào nên tách và tách theo ranh giới nào, giao "
        "tiếp đồng bộ và qua hàng đợi, giao dịch phân tán với saga, và cách quan sát hệ "
        "thống bằng log, metric, trace.\n\nDành cho người đã có kinh nghiệm backend.",
        "backend", MAI_ANH.email, "advanced", 899000,
        _section(
            "Có nên tách không",
            ("Monolith, modular monolith và microservices", 512),
            ("Ranh giới dịch vụ theo nghiệp vụ",
             "Tách theo **tầng kỹ thuật** (một dịch vụ CSDL, một dịch vụ API) chỉ tạo ra "
             "monolith phân tán: mọi thay đổi vẫn phải sửa cùng lúc nhiều nơi. Tách theo "
             "**năng lực nghiệp vụ** — đặt hàng, thanh toán, kho — mỗi dịch vụ sở hữu dữ "
             "liệu của riêng nó.\n\nDấu hiệu ranh giới sai: hai dịch vụ luôn phải triển "
             "khai cùng nhau, hoặc dịch vụ này đọc thẳng bảng của dịch vụ kia."),
        ),
        _section(
            "Dữ liệu và giao tiếp",
            ("Hàng đợi tin nhắn và sự kiện", 567),
            ("Saga thay cho giao dịch phân tán",
             "Không có transaction trải qua nhiều CSDL. **Saga** chia nghiệp vụ thành "
             "chuỗi bước cục bộ, mỗi bước có **hành động bù**: đặt hàng → giữ kho → trừ "
             "tiền; trừ tiền hỏng thì nhả kho và hủy đơn.\n\nMỗi bước phải chịu được việc "
             "nhận cùng một tin nhắn hai lần (idempotent), vì hàng đợi chỉ hứa giao "
             "**ít nhất một lần**."),
        ),
        _section(
            "Vận hành",
            ("Log, metric và distributed tracing", 534),
        ),
    ),
]


def published_days_ago(index: int) -> int:
    """How long ago course number `index` went on sale: spread over the last
    five months, newest first in list order, every one on a different day."""
    return 2 + index * 7


@dataclass(frozen=True, slots=True)
class Written:
    categories: int
    courses: int


async def _ensure_categories(session: AsyncSession) -> int:
    created = 0
    by_slug = {
        category.slug: category
        for category in await session.scalars(select(Category))
    }

    for spec in CATEGORIES:
        if spec.slug in by_slug:
            continue
        parent_id = None
        if spec.parent_slug is not None:
            parent = by_slug.get(spec.parent_slug)
            if parent is None:
                raise SystemExit(
                    f"Chưa có danh mục {spec.parent_slug!r}. "
                    "Chạy `python -m scripts.seed` trước."
                )
            parent_id = parent.id
        siblings = sum(1 for c in by_slug.values() if c.parent_id == parent_id)
        category = Category(
            name=spec.name, slug=spec.slug, parent_id=parent_id, position=siblings
        )
        session.add(category)
        await session.flush()
        by_slug[spec.slug] = category
        created += 1

    return created


async def seed_catalogue(session: AsyncSession, *, now: datetime | None = None) -> Written:
    """Write any missing category and course. Does not commit."""
    now = now or datetime.now(UTC)
    categories_created = await _ensure_categories(session)

    instructors = {
        user.email: user
        for user in await session.scalars(
            select(User).where(User.email.in_([KHOA.email, MAI_ANH.email]))
        )
    }
    if len(instructors) != 2:
        raise SystemExit(
            "Chưa có giảng viên seed (khoa.tran, mai.anh). "
            "Chạy `python -m scripts.seed` trước."
        )

    categories = {
        category.slug: category for category in await session.scalars(select(Category))
    }
    existing = set(
        await session.scalars(
            select(Course.slug).where(Course.slug.in_([c.slug for c in COURSES]))
        )
    )

    hls_url = sample_hls_url()
    created = 0
    for index, spec in enumerate(COURSES):
        if spec.slug in existing:
            continue
        await _build_course(
            session,
            spec,
            instructors[spec.instructor_email],
            categories[spec.category_slug],
            hls_url,
        )
        at = now - timedelta(days=published_days_ago(index))
        # The clock only: the course was written now, as an approval would
        # have left it, then dated to when it "went on sale".
        await session.execute(
            update(Course)
            .where(Course.id == seed_course_id(spec.slug))
            .values(published_at=at, created_at=at - timedelta(days=3))
        )
        created += 1

    await session.flush()
    return Written(categories=categories_created, courses=created)


class PurgeBlocked(Exception):
    """Orders still point at the courses `--purge` would delete."""


async def purge(session: AsyncSession) -> Written:
    """Remove what this script writes. Does not commit."""
    slugs = [course.slug for course in COURSES]
    course_ids = list(
        await session.scalars(select(Course.id).where(Course.slug.in_(slugs)))
    )

    if course_ids:
        blocking = await session.scalar(
            select(func.count(distinct(OrderItem.order_id))).where(
                OrderItem.course_id.in_(course_ids)
            )
        )
        if blocking:
            raise PurgeBlocked(
                f"Không gỡ được: còn {blocking} đơn hàng chứa các khóa này, mà đơn hàng "
                "là sổ tiền nên script này không xóa. Đơn của scripts.seed_sales thì gỡ "
                "trước, rồi chạy lại lệnh này:\n"
                "  python -m scripts.seed_study --purge\n"
                "  python -m scripts.seed_sales --purge\n"
                "Đơn của tài khoản thật thì phải xem và quyết định bằng tay."
            )

        # Enrolments hold on to the course (RESTRICT) and certificates to the
        # enrolment, and by now somebody may have joined a free one by hand.
        await session.execute(delete(Review).where(Review.course_id.in_(course_ids)))
        await certificates.delete_for_enrollments(
            session, select(Enrollment.id).where(Enrollment.course_id.in_(course_ids))
        )
        await session.execute(
            delete(Enrollment).where(Enrollment.course_id.in_(course_ids))
        )
        # Sections, lessons, chunks, embeddings, cart lines... cascade.
        await session.execute(delete(Course).where(Course.id.in_(course_ids)))

    # Lessons let go of their video row (SET NULL); the rows themselves are
    # this script's, found by the key prefix `_build_course` gives them.
    for slug in slugs:
        await session.execute(
            delete(VideoAsset).where(VideoAsset.storage_key.like(f"seed/{slug}/%"))
        )

    # Categories, children before parents, and only once nothing is filed
    # under them: one an admin has since put a course in stays.
    removed = 0
    for spec in reversed(CATEGORIES):
        category = await session.scalar(select(Category).where(Category.slug == spec.slug))
        if category is None:
            continue
        in_use = await session.scalar(
            select(func.count()).select_from(Course).where(Course.category_id == category.id)
        ) or await session.scalar(
            select(func.count()).select_from(Category).where(Category.parent_id == category.id)
        )
        if in_use:
            continue
        await session.delete(category)
        await session.flush()
        removed += 1

    await session.flush()
    return Written(categories=removed, courses=len(course_ids))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Xóa các khóa học và danh mục do script này tạo ra.",
    )
    args = parser.parse_args()

    async with SessionLocal() as session:
        if args.purge:
            try:
                written = await purge(session)
            except PurgeBlocked as blocked:
                print(blocked, file=sys.stderr)
                raise SystemExit(1) from None
            await session.commit()
            print(
                f"Đã xóa {written.courses} khóa học và {written.categories} danh mục."
            )
            return

        written = await seed_catalogue(session)
        await session.commit()

    print(f"danh mục : {written.categories} tạo mới")
    print(f"khóa học : {written.courses} tạo mới (trong {len(COURSES)})")
    if written.courses:
        print(
            "\nCó GEMINI_API_KEY thì chạy tiếp để có \"Khóa học tương tự\" và trợ giảng:\n"
            "  python -m scripts.rebuild_course_embeddings\n"
            "  python -m scripts.ingest_course --all"
        )


if __name__ == "__main__":
    asyncio.run(main())
