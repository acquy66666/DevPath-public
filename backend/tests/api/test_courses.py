"""Course CRUD and the status machine around it.

Two rules run through everything here: a course belongs to exactly one
instructor, and a course nobody may see does not exist as far as the API is
concerned.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Category, Course, User

PASSWORD = "mật-khẩu-đủ-dài"
COURSES = "/api/v1/courses"


async def make_user(session: AsyncSession, role: str, email: str | None = None) -> User:
    user = User(
        email=email or f"{role}@example.com",
        full_name=role.title(),
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


async def make_category(session: AsyncSession, name: str = "Python") -> Category:
    """Unique slug per call: the dev database already holds the seeded tree,
    and `uq_categories_slug` does not care that this is a test."""
    category = Category(name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()
    return category


@pytest.fixture
async def category(db_session: AsyncSession) -> Category:
    return await make_category(db_session)


@pytest.fixture
async def instructor(
    api_client: AsyncClient, db_session: AsyncSession
) -> dict[str, str]:
    return await sign_in(api_client, await make_user(db_session, "instructor"))


@pytest.fixture
async def student(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await sign_in(api_client, await make_user(db_session, "student"))


@pytest.fixture
def manual_review() -> Generator[None, None, None]:
    """Turn the auto-approve flag off, the way Phase 5 will leave it."""
    settings = get_settings()
    original = settings.auto_approve_courses
    object.__setattr__(settings, "auto_approve_courses", False)
    yield
    object.__setattr__(settings, "auto_approve_courses", original)


def payload(category: Category, **overrides) -> dict:
    return {
        "title": "Lập trình Python cơ bản",
        "category_id": str(category.id),
        "subtitle": "Từ số không tới viết được chương trình đầu tiên",
        "description": "## Nội dung\nBiến, vòng lặp, hàm.",
        "price": "499000.00",
        "level": "beginner",
        **overrides,
    }


async def create_course(
    client: AsyncClient, headers: dict[str, str], category: Category, **overrides
) -> dict:
    """Create a course, and say so out loud when creating one fails.

    Every caller goes straight on to `created["id"]`. Returning the body
    unchecked meant a failed POST surfaced two lines later as `KeyError: 'id'`,
    which names neither the status nor the reason -- and once, on a full run
    that has not repeated, that was the only thing left of the failure.
    """
    response = await client.post(
        COURSES, json=payload(category, **overrides), headers=headers
    )
    assert response.status_code == 201, f"{response.status_code}: {response.text}"
    return response.json()


# --- Creating --------------------------------------------------------------


async def test_an_instructor_creates_a_draft(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    response = await api_client.post(
        COURSES, json=payload(category), headers=instructor
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Lập trình Python cơ bản"
    assert body["status"] == "draft"
    assert body["published_at"] is None


async def test_a_new_course_belongs_to_its_creator(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    """The body has no instructor_id to send, and the service ignores the idea."""
    body = await create_course(api_client, instructor, category)

    course = await db_session.get(Course, uuid.UUID(body["id"]))
    owner = await db_session.scalar(
        select(User).where(User.email == "instructor@example.com")
    )
    assert course.instructor_id == owner.id


async def test_the_slug_comes_from_the_title(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    body = await create_course(api_client, instructor, category)

    assert body["slug"].startswith("lap-trinh-python-co-ban-")


async def test_two_courses_with_one_title_get_different_slugs(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    first = await create_course(api_client, instructor, category)
    second = await create_course(api_client, instructor, category)

    assert first["slug"] != second["slug"]


async def test_a_student_cannot_create_a_course(
    api_client: AsyncClient, student: dict[str, str], category: Category
) -> None:
    response = await api_client.post(COURSES, json=payload(category), headers=student)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


async def test_creating_a_course_requires_signing_in(
    api_client: AsyncClient, category: Category
) -> None:
    response = await api_client.post(COURSES, json=payload(category))

    assert response.status_code == 401


async def test_a_course_needs_a_category_that_exists(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    response = await api_client.post(
        COURSES,
        json=payload(category, category_id=str(uuid.uuid4())),
        headers=instructor,
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CATEGORY_NOT_FOUND"


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("title", "x" * 201),
        ("price", "-1"),
        ("level", "expert"),
    ],
)
async def test_the_body_is_validated(
    api_client: AsyncClient,
    instructor: dict[str, str],
    category: Category,
    field: str,
    value: str,
) -> None:
    response = await api_client.post(
        COURSES, json=payload(category, **{field: value}), headers=instructor
    )

    assert response.status_code == 422


async def test_price_is_kept_to_the_cent(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    """Money is NUMERIC all the way; a float would round somebody's invoice."""
    body = await create_course(api_client, instructor, category, price="1999999.99")

    assert body["price"] == "1999999.99"


# --- Reading ---------------------------------------------------------------


async def test_the_owner_sees_their_own_draft(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    created = await create_course(api_client, instructor, category)

    response = await api_client.get(f"{COURSES}/{created['id']}", headers=instructor)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_a_draft_does_not_exist_for_anybody_else(
    api_client: AsyncClient,
    instructor: dict[str, str],
    student: dict[str, str],
    category: Category,
) -> None:
    """404, not 403: a draft nobody may read should not even be confirmed."""
    created = await create_course(api_client, instructor, category)

    response = await api_client.get(f"{COURSES}/{created['id']}", headers=student)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_a_published_course_is_public(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    created = await create_course(api_client, instructor, category)
    await api_client.post(f"{COURSES}/{created['id']}/submit", headers=instructor)

    response = await api_client.get(f"{COURSES}/{created['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "published"


async def test_an_unknown_course_is_a_404(
    api_client: AsyncClient, instructor: dict[str, str]
) -> None:
    response = await api_client.get(f"{COURSES}/{uuid.uuid4()}", headers=instructor)

    assert response.status_code == 404


# --- The instructor's own list ---------------------------------------------


async def test_the_list_holds_only_your_own_courses(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    await create_course(api_client, instructor, category, title="Của tôi")
    other = await make_user(db_session, "instructor", "khac@example.com")
    other_headers = await sign_in(api_client, other)
    await create_course(api_client, other_headers, category, title="Của người khác")

    response = await api_client.get(f"{COURSES}/me", headers=instructor)

    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Của tôi"]


async def test_the_list_is_paginated(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    for index in range(3):
        await create_course(api_client, instructor, category, title=f"Khóa {index}")

    response = await api_client.get(
        f"{COURSES}/me", params={"page": 2, "page_size": 2}, headers=instructor
    )

    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["items"]) == 1


async def test_the_newest_course_comes_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    """created_at is set by Postgres `now()`, which is the *transaction* clock —
    inside one test transaction every row would share it, so the newer course
    gets its timestamp moved on purpose."""
    await create_course(api_client, instructor, category, title="Cũ")
    newer = await create_course(api_client, instructor, category, title="Mới")
    row = await db_session.get(Course, uuid.UUID(newer["id"]))
    row.created_at = datetime.now(tz=UTC) + timedelta(minutes=1)
    await db_session.flush()

    response = await api_client.get(f"{COURSES}/me", headers=instructor)

    assert [item["title"] for item in response.json()["items"]] == ["Mới", "Cũ"]


async def test_listing_your_courses_requires_signing_in(api_client: AsyncClient) -> None:
    assert (await api_client.get(f"{COURSES}/me")).status_code == 401


# --- Editing ---------------------------------------------------------------


async def test_the_owner_edits_their_course(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    created = await create_course(api_client, instructor, category)

    response = await api_client.patch(
        f"{COURSES}/{created['id']}",
        json={"title": "Tên mới", "price": "0"},
        headers=instructor,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Tên mới"
    assert response.json()["price"] == "0.00"


async def test_editing_leaves_the_fields_you_did_not_send(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    created = await create_course(api_client, instructor, category)

    body = (
        await api_client.patch(
            f"{COURSES}/{created['id']}", json={"title": "Tên mới"}, headers=instructor
        )
    ).json()

    assert body["subtitle"] == created["subtitle"]
    assert body["slug"] == created["slug"]


async def test_the_slug_does_not_move_when_the_title_does(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    """A URL that has been shared has to keep working."""
    created = await create_course(api_client, instructor, category)

    body = (
        await api_client.patch(
            f"{COURSES}/{created['id']}", json={"title": "Hoàn toàn khác"},
            headers=instructor,
        )
    ).json()

    assert body["slug"] == created["slug"]


async def test_status_cannot_be_set_by_editing(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    """Publishing is a transition with rules, not a field to overwrite."""
    created = await create_course(api_client, instructor, category)

    body = (
        await api_client.patch(
            f"{COURSES}/{created['id']}",
            json={"status": "published", "instructor_id": str(uuid.uuid4())},
            headers=instructor,
        )
    ).json()

    assert body["status"] == "draft"


@pytest.mark.parametrize("field", ["title", "category_id", "price", "level"])
async def test_a_patch_cannot_empty_a_required_field(
    api_client: AsyncClient,
    instructor: dict[str, str],
    category: Category,
    field: str,
) -> None:
    """`null` in a PATCH means "clear it", and these columns are NOT NULL —
    better a 422 naming the field than a 500 from Postgres."""
    created = await create_course(api_client, instructor, category)

    response = await api_client.patch(
        f"{COURSES}/{created['id']}", json={field: None}, headers=instructor
    )

    assert response.status_code == 422


async def test_another_instructor_cannot_edit_your_course(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    created = await create_course(api_client, instructor, category)
    other = await sign_in(
        api_client, await make_user(db_session, "instructor", "khac@example.com")
    )

    response = await api_client.patch(
        f"{COURSES}/{created['id']}", json={"title": "Cướp khóa học"}, headers=other
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


# --- Deleting --------------------------------------------------------------


async def test_deleting_hides_the_course_without_erasing_it(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    """Soft delete: students who already paid keep watching."""
    created = await create_course(api_client, instructor, category)

    response = await api_client.delete(f"{COURSES}/{created['id']}", headers=instructor)

    assert response.status_code == 204
    course = await db_session.get(Course, uuid.UUID(created["id"]))
    assert course is not None
    assert course.deleted_at is not None


async def test_a_deleted_course_is_gone_from_the_api(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    created = await create_course(api_client, instructor, category)
    await api_client.delete(f"{COURSES}/{created['id']}", headers=instructor)

    detail = await api_client.get(f"{COURSES}/{created['id']}", headers=instructor)
    listing = await api_client.get(f"{COURSES}/me", headers=instructor)

    assert detail.status_code == 404
    assert listing.json()["total"] == 0


async def test_an_admin_can_take_a_course_down(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    created = await create_course(api_client, instructor, category)
    admin = await sign_in(api_client, await make_user(db_session, "admin"))

    response = await api_client.delete(f"{COURSES}/{created['id']}", headers=admin)

    assert response.status_code == 204


async def test_another_instructor_cannot_delete_your_course(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    created = await create_course(api_client, instructor, category)
    other = await sign_in(
        api_client, await make_user(db_session, "instructor", "khac@example.com")
    )

    response = await api_client.delete(f"{COURSES}/{created['id']}", headers=other)

    assert response.status_code == 403


# --- The status machine ----------------------------------------------------


async def test_submitting_publishes_while_auto_approve_is_on(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    """Phase 5 replaces the flag with a real admin queue."""
    created = await create_course(api_client, instructor, category)

    response = await api_client.post(
        f"{COURSES}/{created['id']}/submit", headers=instructor
    )

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["published_at"] is not None


async def test_submitting_waits_for_review_when_the_flag_is_off(
    api_client: AsyncClient,
    instructor: dict[str, str],
    category: Category,
    manual_review: None,
) -> None:
    created = await create_course(api_client, instructor, category)

    response = await api_client.post(
        f"{COURSES}/{created['id']}/submit", headers=instructor
    )

    assert response.json()["status"] == "pending_review"
    assert response.json()["published_at"] is None


async def test_a_published_course_cannot_be_submitted_again(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    created = await create_course(api_client, instructor, category)
    await api_client.post(f"{COURSES}/{created['id']}/submit", headers=instructor)

    response = await api_client.post(
        f"{COURSES}/{created['id']}/submit", headers=instructor
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_COURSE_STATUS"


async def test_unpublishing_returns_a_course_to_draft(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    """Taking a course off the shelf, which the spec spells published -> draft."""
    created = await create_course(api_client, instructor, category)
    await api_client.post(f"{COURSES}/{created['id']}/submit", headers=instructor)

    response = await api_client.post(
        f"{COURSES}/{created['id']}/unpublish", headers=instructor
    )

    assert response.status_code == 200
    assert response.json()["status"] == "draft"


async def test_a_draft_cannot_be_unpublished(
    api_client: AsyncClient, instructor: dict[str, str], category: Category
) -> None:
    created = await create_course(api_client, instructor, category)

    response = await api_client.post(
        f"{COURSES}/{created['id']}/unpublish", headers=instructor
    )

    assert response.status_code == 409


async def test_only_the_owner_moves_a_course_through_its_states(
    api_client: AsyncClient,
    db_session: AsyncSession,
    instructor: dict[str, str],
    category: Category,
) -> None:
    created = await create_course(api_client, instructor, category)
    other = await sign_in(
        api_client, await make_user(db_session, "instructor", "khac@example.com")
    )

    response = await api_client.post(f"{COURSES}/{created['id']}/submit", headers=other)

    assert response.status_code == 403
