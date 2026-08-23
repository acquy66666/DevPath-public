"""The public course page: one course, found by the slug in its URL.

The address is the point of this endpoint. Everything else it does -- who may
see a draft, what a stranger is told about one -- already holds for `GET
/courses/{id}`, and is checked here again because a second door into the same
room is exactly where such a rule goes missing.
"""

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, CourseSection, Lesson, User

PASSWORD = "mật-khẩu-đủ-dài"
BY_SLUG = "/api/v1/courses/by-slug"


async def make_user(session: AsyncSession, role: str, full_name: str = "Giảng viên") -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=full_name,
        password_hash=hash_password(PASSWORD),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def sign_in(client: AsyncClient, user: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_course(
    session: AsyncSession,
    owner: User,
    *,
    status: str = "published",
    category_name: str = "Lập trình Python",
) -> tuple[Course, Category]:
    category = Category(
        name=category_name, slug=f"danh-muc-{uuid.uuid4().hex[:8]}"
    )
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=owner.id,
        category_id=category.id,
        title="Python cho người mới bắt đầu",
        slug=f"python-co-ban-{uuid.uuid4().hex[:8]}",
        subtitle="Từ biến đến vòng lặp trong 6 giờ",
        description="Khóa học nhập môn.",
        status=status,
        published_at=datetime.now(UTC) if status == "published" else None,
    )
    session.add(course)
    await session.flush()
    return course, category


async def test_a_published_course_is_public(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """No token at all: this is the page a search engine lands on."""
    owner = await make_user(db_session, "instructor")
    course, _ = await make_course(db_session, owner)

    response = await api_client.get(f"{BY_SLUG}/{course.slug}")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == course.slug
    assert body["title"] == "Python cho người mới bắt đầu"
    assert body["subtitle"] == "Từ biến đến vòng lặp trong 6 giờ"


async def test_the_instructor_comes_embedded_and_without_an_email(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The page needs a name and a face. It does not need the address."""
    owner = await make_user(db_session, "instructor", full_name="Nguyễn Văn A")
    owner.avatar_url = "https://cdn.example/avatars/x/anh.png"
    course, _ = await make_course(db_session, owner)

    body = (await api_client.get(f"{BY_SLUG}/{course.slug}")).json()

    assert body["instructor"]["full_name"] == "Nguyễn Văn A"
    assert body["instructor"]["avatar_url"] == "https://cdn.example/avatars/x/anh.png"
    assert "email" not in body["instructor"]
    assert "password_hash" not in body["instructor"]


async def test_the_category_comes_embedded(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Named, not an id: the page draws a breadcrumb, not a UUID."""
    owner = await make_user(db_session, "instructor")
    course, category = await make_course(db_session, owner)

    body = (await api_client.get(f"{BY_SLUG}/{course.slug}")).json()

    assert body["category"]["name"] == "Lập trình Python"
    assert body["category"]["slug"] == category.slug
    assert body["category_id"] == str(category.id)


async def test_a_draft_is_not_found_by_a_stranger(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """404, not 403: an unpublished course should not be confirmed to exist."""
    owner = await make_user(db_session, "instructor")
    course, _ = await make_course(db_session, owner, status="draft")

    anonymous = await api_client.get(f"{BY_SLUG}/{course.slug}")
    assert anonymous.status_code == 404
    assert anonymous.json()["detail"]["code"] == "COURSE_NOT_FOUND"

    student = await make_user(db_session, "student")
    signed_in = await api_client.get(
        f"{BY_SLUG}/{course.slug}", headers=await sign_in(api_client, student)
    )
    assert signed_in.status_code == 404


async def test_the_owner_can_open_their_own_draft(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """So the page can be checked before anyone else can reach it."""
    owner = await make_user(db_session, "instructor")
    course, _ = await make_course(db_session, owner, status="draft")

    response = await api_client.get(
        f"{BY_SLUG}/{course.slug}", headers=await sign_in(api_client, owner)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "draft"


async def test_an_admin_can_open_a_draft(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await make_user(db_session, "instructor")
    course, _ = await make_course(db_session, owner, status="draft")
    admin = await make_user(db_session, "admin")

    response = await api_client.get(
        f"{BY_SLUG}/{course.slug}", headers=await sign_in(api_client, admin)
    )

    assert response.status_code == 200


async def test_an_unknown_slug_is_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await api_client.get(f"{BY_SLUG}/khong-co-khoa-hoc-nao-ten-nay")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_a_soft_deleted_course_is_gone_even_though_it_was_published(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The URL was public and may still be linked; it must stop answering."""
    owner = await make_user(db_session, "instructor")
    course, _ = await make_course(db_session, owner)
    course.deleted_at = datetime.now(UTC)
    await db_session.flush()

    response = await api_client.get(f"{BY_SLUG}/{course.slug}")

    assert response.status_code == 404


async def test_the_table_of_contents_says_which_lessons_are_free(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The page marks preview lessons, so the public tree has to carry the flag."""
    owner = await make_user(db_session, "instructor")
    course, _ = await make_course(db_session, owner)

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    db_session.add(section)
    await db_session.flush()
    db_session.add_all(
        [
            Lesson(
                section_id=section.id,
                title="Bài mở đầu",
                type="video",
                position=0,
                is_preview=True,
            ),
            Lesson(
                section_id=section.id,
                title="Bài trả phí",
                type="video",
                position=1,
                is_preview=False,
            ),
        ]
    )
    await db_session.flush()

    response = await api_client.get(f"/api/v1/courses/{course.id}/curriculum")

    assert response.status_code == 200
    lessons = response.json()["sections"][0]["lessons"]
    assert [lesson["is_preview"] for lesson in lessons] == [True, False]
    # The tree stays a table of contents: no lesson body travels with it.
    assert "article_content" not in lessons[0]
