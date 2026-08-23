"""The public catalogue: what it finds, what it hides, and in what order.

Every test scopes itself -- by a nonsense word in the title, or by its own
category -- because this endpoint reads the whole `courses` table and a
developer's database already has seeded courses in it.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, User

PASSWORD = "mật-khẩu-đủ-dài"
CATALOG = "/api/v1/courses"


@pytest.fixture
async def instructor(db_session: AsyncSession) -> User:
    user = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Trần Thị B",
        password_hash=hash_password(PASSWORD),
        role="instructor",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def category(db_session: AsyncSession) -> Category:
    row = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    db_session.add(row)
    await db_session.flush()
    return row


async def make_course(
    session: AsyncSession,
    owner: User,
    category: Category,
    *,
    title: str,
    subtitle: str | None = None,
    description: str | None = None,
    price: str = "0",
    rating_avg: str = "0",
    rating_count: int = 0,
    status: str = "published",
    published_at: datetime | None = None,
    rejection_reason: str | None = None,
) -> Course:
    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title=title,
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        subtitle=subtitle,
        description=description,
        price=Decimal(price),
        rating_avg=Decimal(rating_avg),
        rating_count=rating_count,
        status=status,
        # ck_courses_published_at and ck_courses_rejection_reason both bite at
        # INSERT, so these cannot be filled in afterwards.
        published_at=(
            (published_at or datetime.now(UTC)) if status == "published" else None
        ),
        rejection_reason=(
            rejection_reason or ("Thiếu nội dung" if status == "rejected" else None)
        ),
    )
    session.add(course)
    await session.flush()
    return course


def titles(body: dict) -> list[str]:
    return [item["title"] for item in body["items"]]


# --- Searching -------------------------------------------------------------


async def test_a_course_is_found_by_a_word_in_its_title(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(db_session, instructor, category, title="Lập trình Zorblax")

    response = await api_client.get(CATALOG, params={"q": "Zorblax"})

    assert response.status_code == 200
    assert titles(response.json()) == ["Lập trình Zorblax"]


async def test_search_ignores_diacritics_in_both_directions(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    """People type "lap trinh" and mean "Lập trình". Both spellings must meet."""
    await make_course(db_session, instructor, category, title="Lập trình Zorblax")

    without = await api_client.get(CATALOG, params={"q": "lap trinh zorblax"})
    with_marks = await api_client.get(CATALOG, params={"q": "Lập trình Zorblax"})

    assert titles(without.json()) == ["Lập trình Zorblax"]
    assert titles(with_marks.json()) == ["Lập trình Zorblax"]


async def test_the_subtitle_and_the_description_are_searchable_too(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(
        db_session, instructor, category, title="Khóa A", subtitle="Học về Zorblax"
    )
    await make_course(
        db_session, instructor, category, title="Khóa B", description="Chương cuối nói về Zorblax."
    )

    body = (await api_client.get(CATALOG, params={"q": "Zorblax"})).json()

    assert sorted(titles(body)) == ["Khóa A", "Khóa B"]


async def test_a_title_match_outranks_a_description_match(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    """This is what the A/B/C weights in the trigger are for."""
    await make_course(
        db_session, instructor, category, title="Nhập môn", description="Có nhắc Zorblax."
    )
    await make_course(db_session, instructor, category, title="Zorblax toàn tập")

    body = (await api_client.get(CATALOG, params={"q": "Zorblax"})).json()

    assert titles(body)[0] == "Zorblax toàn tập"


async def test_the_vector_follows_an_edit(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    """The trigger fires on update, so a renamed course is found by its new name."""
    course = await make_course(db_session, instructor, category, title="Tên Zorblax cũ")
    course.title = "Tên Quixotel mới"
    await db_session.flush()

    stale = await api_client.get(CATALOG, params={"q": "Zorblax"})
    fresh = await api_client.get(CATALOG, params={"q": "Quixotel"})

    assert titles(stale.json()) == []
    assert titles(fresh.json()) == ["Tên Quixotel mới"]


async def test_a_search_that_matches_nothing_is_an_empty_page(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(db_session, instructor, category, title="Lập trình Zorblax")

    body = (await api_client.get(CATALOG, params={"q": "Khongcotukhoanay"})).json()

    assert body["items"] == []
    assert body["total"] == 0


# --- Filtering -------------------------------------------------------------


async def test_a_category_filter_includes_its_children(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    """Picking "Lập trình" has to bring "Python" with it."""
    child = Category(
        name="Python", slug=f"python-{uuid.uuid4().hex[:8]}", parent_id=category.id
    )
    db_session.add(child)
    await db_session.flush()

    await make_course(db_session, instructor, category, title="Khóa cha")
    await make_course(db_session, instructor, child, title="Khóa con")

    body = (
        await api_client.get(CATALOG, params={"category_id": str(category.id)})
    ).json()

    assert sorted(titles(body)) == ["Khóa cha", "Khóa con"]


async def test_a_category_with_nothing_in_it_is_empty_not_an_error(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A stale bookmark should show "không có khóa học nào", not a 404."""
    response = await api_client.get(CATALOG, params={"category_id": str(uuid.uuid4())})

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_the_price_range_is_inclusive_at_both_ends(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(db_session, instructor, category, title="Miễn phí", price="0")
    await make_course(db_session, instructor, category, title="Vừa", price="200000")
    await make_course(db_session, instructor, category, title="Đắt", price="900000")

    body = (
        await api_client.get(
            CATALOG,
            params={
                "category_id": str(category.id),
                "price_min": "0",
                "price_max": "200000",
            },
        )
    ).json()

    assert sorted(titles(body)) == ["Miễn phí", "Vừa"]


async def test_free_courses_are_a_price_ceiling_of_zero(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(db_session, instructor, category, title="Miễn phí", price="0")
    await make_course(db_session, instructor, category, title="Có phí", price="500000")

    body = (
        await api_client.get(
            CATALOG, params={"category_id": str(category.id), "price_max": "0"}
        )
    ).json()

    assert titles(body) == ["Miễn phí"]


async def test_a_rating_floor_drops_everything_below_it(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(
        db_session, instructor, category, title="Tốt", rating_avg="4.60", rating_count=20
    )
    await make_course(
        db_session, instructor, category, title="Tạm", rating_avg="3.20", rating_count=8
    )
    # No reviews yet means 0.00, which is not the same as bad -- but a filter
    # asking for 4+ cannot honestly include it either.
    await make_course(db_session, instructor, category, title="Chưa có đánh giá")

    body = (
        await api_client.get(
            CATALOG, params={"category_id": str(category.id), "rating_min": "4"}
        )
    ).json()

    assert titles(body) == ["Tốt"]


async def test_filters_combine(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(
        db_session,
        instructor,
        category,
        title="Zorblax nâng cao",
        price="300000",
        rating_avg="4.80",
        rating_count=10,
    )
    await make_course(
        db_session, instructor, category, title="Zorblax giá cao", price="2000000",
        rating_avg="4.90", rating_count=10,
    )
    await make_course(
        db_session, instructor, category, title="Zorblax ít sao", price="300000"
    )

    body = (
        await api_client.get(
            CATALOG,
            params={"q": "Zorblax", "price_max": "500000", "rating_min": "4"},
        )
    ).json()

    assert titles(body) == ["Zorblax nâng cao"]


# --- What never appears ----------------------------------------------------


@pytest.mark.parametrize("status", ["draft", "pending_review", "rejected"])
async def test_only_published_courses_are_listed(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: User,
    category: Category,
    status: str,
) -> None:
    await make_course(
        db_session, instructor, category, title="Zorblax chưa xong", status=status
    )

    body = (await api_client.get(CATALOG, params={"q": "Zorblax"})).json()

    assert body["items"] == []


async def test_a_soft_deleted_course_leaves_the_catalogue(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    course = await make_course(db_session, instructor, category, title="Zorblax đã gỡ")
    course.deleted_at = datetime.now(UTC)
    await db_session.flush()

    body = (await api_client.get(CATALOG, params={"q": "Zorblax"})).json()

    assert body["items"] == []


async def test_the_listing_carries_no_email(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(db_session, instructor, category, title="Zorblax công khai")

    item = (await api_client.get(CATALOG, params={"q": "Zorblax"})).json()["items"][0]

    assert item["instructor"]["full_name"] == "Trần Thị B"
    assert "email" not in item["instructor"]
    # A card is a card: the long text belongs to the detail page.
    assert "description" not in item


# --- Order and paging ------------------------------------------------------


async def test_a_bare_listing_is_newest_first(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    now = datetime.now(UTC)
    await make_course(
        db_session, instructor, category, title="Cũ", published_at=now - timedelta(days=30)
    )
    await make_course(
        db_session, instructor, category, title="Mới", published_at=now - timedelta(days=1)
    )

    body = (
        await api_client.get(CATALOG, params={"category_id": str(category.id)})
    ).json()

    assert titles(body) == ["Mới", "Cũ"]


async def test_sorting_by_rating_puts_the_best_first(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    await make_course(
        db_session, instructor, category, title="Ba sao", rating_avg="3.00", rating_count=5
    )
    await make_course(
        db_session, instructor, category, title="Năm sao", rating_avg="4.90", rating_count=5
    )

    body = (
        await api_client.get(
            CATALOG, params={"category_id": str(category.id), "sort": "rating"}
        )
    ).json()

    assert titles(body) == ["Năm sao", "Ba sao"]


async def test_paging_reports_the_total_before_the_page(
    api_client: AsyncClient, db_session: AsyncSession, instructor: User, category: Category
) -> None:
    now = datetime.now(UTC)
    for index in range(3):
        await make_course(
            db_session,
            instructor,
            category,
            title=f"Zorblax {index}",
            published_at=now - timedelta(days=index),
        )

    first = (
        await api_client.get(CATALOG, params={"q": "Zorblax", "page_size": 2})
    ).json()
    second = (
        await api_client.get(
            CATALOG, params={"q": "Zorblax", "page_size": 2, "page": 2}
        )
    ).json()

    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    # No course appears on both pages.
    assert set(titles(first)) & set(titles(second)) == set()


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"rating_min": "6"},
        {"price_min": "-1"},
        {"sort": "gia-re-nhat"},
    ],
)
async def test_nonsense_parameters_are_refused(
    api_client: AsyncClient, db_session: AsyncSession, params: dict
) -> None:
    response = await api_client.get(CATALOG, params=params)

    assert response.status_code == 422
