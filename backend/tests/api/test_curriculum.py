"""Sections and lessons: building the curriculum, and reordering it.

Ordering is the part worth testing hardest. `position` is what the instructor
drags around, and every rearrangement rewrites several rows at once -- the kind
of operation that looks fine until two rows briefly want the same slot.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, CourseSection, Lesson, User

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


@pytest.fixture
async def owner(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await sign_in(api_client, await make_user(db_session, "instructor"))


@pytest.fixture
async def course(
    api_client: AsyncClient, db_session: AsyncSession, owner: dict[str, str]
) -> dict:
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()

    response = await api_client.post(
        COURSES,
        json={"title": "Lập trình Python cơ bản", "category_id": str(category.id)},
        headers=owner,
    )
    return response.json()


async def add_section(
    client: AsyncClient, course: dict, headers: dict[str, str], title: str
) -> dict:
    response = await client.post(
        f"{COURSES}/{course['id']}/sections", json={"title": title}, headers=headers
    )
    return response.json()


async def add_lesson(
    client: AsyncClient,
    section: dict,
    headers: dict[str, str],
    title: str,
    **overrides,
) -> dict:
    response = await client.post(
        f"/api/v1/sections/{section['id']}/lessons",
        json={"title": title, "type": "article", **overrides},
        headers=headers,
    )
    return response.json()


async def curriculum(
    client: AsyncClient, course: dict, headers: dict[str, str] | None = None
) -> dict:
    response = await client.get(
        f"{COURSES}/{course['id']}/curriculum", headers=headers or {}
    )
    return response.json()


# --- Sections --------------------------------------------------------------


async def test_a_section_is_appended_to_the_end(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    first = await add_section(api_client, course, owner, "Mở đầu")
    second = await add_section(api_client, course, owner, "Biến và kiểu dữ liệu")

    assert first["position"] == 0
    assert second["position"] == 1


async def test_sections_come_back_in_order(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    for title in ("Mở đầu", "Vòng lặp", "Hàm"):
        await add_section(api_client, course, owner, title)

    tree = await curriculum(api_client, course, owner)

    assert [s["title"] for s in tree["sections"]] == ["Mở đầu", "Vòng lặp", "Hàm"]


async def test_a_section_can_be_renamed(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    section = await add_section(api_client, course, owner, "Sai tên")

    response = await api_client.patch(
        f"/api/v1/sections/{section['id']}", json={"title": "Tên đúng"}, headers=owner
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Tên đúng"


async def test_deleting_a_section_closes_the_gap(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """Positions stay 0,1,2… so the next append does not land on a used slot."""
    first = await add_section(api_client, course, owner, "Một")
    await add_section(api_client, course, owner, "Hai")
    await add_section(api_client, course, owner, "Ba")

    await api_client.delete(f"/api/v1/sections/{first['id']}", headers=owner)

    tree = await curriculum(api_client, course, owner)
    assert [(s["title"], s["position"]) for s in tree["sections"]] == [
        ("Hai", 0),
        ("Ba", 1),
    ]


async def test_deleting_a_section_takes_its_lessons_with_it(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    section = await add_section(api_client, course, owner, "Sẽ xóa")
    lesson = await add_lesson(api_client, section, owner, "Bài 1")

    await api_client.delete(f"/api/v1/sections/{section['id']}", headers=owner)

    assert await db_session.get(Lesson, uuid.UUID(lesson["id"])) is None


async def test_sections_are_reordered_as_a_whole(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """The client sends the arrangement it wants, not a series of swaps."""
    one = await add_section(api_client, course, owner, "Một")
    two = await add_section(api_client, course, owner, "Hai")
    three = await add_section(api_client, course, owner, "Ba")

    response = await api_client.put(
        f"{COURSES}/{course['id']}/sections/order",
        json={"section_ids": [three["id"], one["id"], two["id"]]},
        headers=owner,
    )

    assert response.status_code == 200
    tree = await curriculum(api_client, course, owner)
    assert [s["title"] for s in tree["sections"]] == ["Ba", "Một", "Hai"]
    assert [s["position"] for s in tree["sections"]] == [0, 1, 2]


async def test_a_reorder_must_list_every_section_exactly_once(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """A partial list would silently leave rows behind at stale positions."""
    one = await add_section(api_client, course, owner, "Một")
    await add_section(api_client, course, owner, "Hai")

    response = await api_client.put(
        f"{COURSES}/{course['id']}/sections/order",
        json={"section_ids": [one["id"]]},
        headers=owner,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_ORDER"


async def test_a_reorder_cannot_smuggle_in_another_courses_section(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    mine = await add_section(api_client, course, owner, "Của tôi")
    other_course = Category(name="Khác", slug=f"khac-{uuid.uuid4().hex[:8]}")
    db_session.add(other_course)
    await db_session.flush()
    other = (
        await api_client.post(
            COURSES,
            json={"title": "Khóa khác", "category_id": str(other_course.id)},
            headers=owner,
        )
    ).json()
    stranger = await add_section(api_client, other, owner, "Của khóa khác")

    response = await api_client.put(
        f"{COURSES}/{course['id']}/sections/order",
        json={"section_ids": [mine["id"], stranger["id"]]},
        headers=owner,
    )

    assert response.status_code == 400


# --- Lessons ---------------------------------------------------------------


async def test_a_lesson_is_appended_to_its_section(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    section = await add_section(api_client, course, owner, "Mở đầu")

    first = await add_lesson(api_client, section, owner, "Bài 1")
    second = await add_lesson(api_client, section, owner, "Bài 2")

    assert (first["position"], second["position"]) == (0, 1)


async def test_positions_are_counted_per_section(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """Two sections both start at 0; the unique index is on (section, position)."""
    first_section = await add_section(api_client, course, owner, "Một")
    second_section = await add_section(api_client, course, owner, "Hai")

    a = await add_lesson(api_client, first_section, owner, "Bài A")
    b = await add_lesson(api_client, second_section, owner, "Bài B")

    assert a["position"] == b["position"] == 0


async def test_a_video_lesson_starts_without_a_video(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """Upload comes next; the lesson exists first so there is something to
    attach the file to."""
    section = await add_section(api_client, course, owner, "Mở đầu")

    lesson = await add_lesson(api_client, section, owner, "Bài video", type="video")

    assert lesson["type"] == "video"
    assert lesson["video_asset_id"] is None


async def test_a_code_exercise_lesson_starts_as_an_empty_shell(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """Buildable here, filled in elsewhere.

    The statement, the limits and the answer key belong to the grading
    endpoints -- the test cases especially, which must never travel through a
    schema the whole curriculum is rendered with."""
    section = await add_section(api_client, course, owner, "Mở đầu")

    lesson = await add_lesson(
        api_client, section, owner, "Bài tập: tổng hai số", type="code_exercise"
    )

    assert lesson["type"] == "code_exercise"
    assert lesson["article_content"] is None


async def test_a_lesson_type_without_a_feature_behind_it_cannot_be_created(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """A lesson type is buildable once the feature that fills it exists.

    `code_exercise` became buildable in Phase 3, when the exercise, its limits
    and its test cases got endpoints of their own; `quiz` joined it in Phase 4
    on the same terms (see the test below). What is left here is the case that
    never becomes buildable: a type nothing in the system has ever heard of."""
    section = await add_section(api_client, course, owner, "Mở đầu")

    response = await api_client.post(
        f"/api/v1/sections/{section['id']}/lessons",
        json={"title": "Bài", "type": "khong-ton-tai"},
        headers=owner,
    )

    assert response.status_code == 422


async def test_a_quiz_lesson_can_be_built_now_that_quizzes_exist(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """The shell a quiz hangs off.

    It stayed un-buildable through Phases 2 and 3 because an empty shell
    nothing can fill is a dead end rather than a feature. `tests/api/test_quiz.py`
    is the thing that fills it: the quiz, its questions and the attempt flow."""
    section = await add_section(api_client, course, owner, "Mở đầu")

    response = await api_client.post(
        f"/api/v1/sections/{section['id']}/lessons",
        json={"title": "Kiểm tra chương 1", "type": "quiz"},
        headers=owner,
    )

    assert response.status_code == 201, response.text
    assert response.json()["type"] == "quiz"


async def test_a_lesson_can_be_edited(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    section = await add_section(api_client, course, owner, "Mở đầu")
    lesson = await add_lesson(api_client, section, owner, "Bài 1")

    response = await api_client.patch(
        f"/api/v1/lessons/{lesson['id']}",
        json={"title": "Bài 1 (sửa)", "is_preview": True, "article_content": "# Nội dung"},
        headers=owner,
    )

    body = response.json()
    assert body["title"] == "Bài 1 (sửa)"
    assert body["is_preview"] is True
    assert body["article_content"] == "# Nội dung"


async def test_deleting_a_lesson_closes_the_gap(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    section = await add_section(api_client, course, owner, "Mở đầu")
    first = await add_lesson(api_client, section, owner, "Bài 1")
    await add_lesson(api_client, section, owner, "Bài 2")

    await api_client.delete(f"/api/v1/lessons/{first['id']}", headers=owner)

    tree = await curriculum(api_client, course, owner)
    lessons = tree["sections"][0]["lessons"]
    assert [(item["title"], item["position"]) for item in lessons] == [("Bài 2", 0)]


async def test_lessons_are_reordered_within_a_section(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    section = await add_section(api_client, course, owner, "Mở đầu")
    one = await add_lesson(api_client, section, owner, "Một")
    two = await add_lesson(api_client, section, owner, "Hai")

    response = await api_client.put(
        f"/api/v1/sections/{section['id']}/lessons/order",
        json={"lesson_ids": [two["id"], one["id"]]},
        headers=owner,
    )

    assert response.status_code == 200
    tree = await curriculum(api_client, course, owner)
    assert [item["title"] for item in tree["sections"][0]["lessons"]] == ["Hai", "Một"]


async def test_a_lesson_can_be_dragged_into_another_section(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    """The reorder payload is "these lessons, in this order, in this section",
    which is exactly what a drop into a different column means."""
    first_section = await add_section(api_client, course, owner, "Một")
    second_section = await add_section(api_client, course, owner, "Hai")
    moving = await add_lesson(api_client, first_section, owner, "Chuyển đi")
    staying = await add_lesson(api_client, second_section, owner, "Ở lại")

    response = await api_client.put(
        f"/api/v1/sections/{second_section['id']}/lessons/order",
        json={"lesson_ids": [moving["id"], staying["id"]]},
        headers=owner,
    )

    assert response.status_code == 200
    row = await db_session.get(Lesson, uuid.UUID(moving["id"]))
    await db_session.refresh(row)
    assert row.section_id == uuid.UUID(second_section["id"])
    assert row.position == 0

    tree = await curriculum(api_client, course, owner)
    assert tree["sections"][0]["lessons"] == []
    assert [item["title"] for item in tree["sections"][1]["lessons"]] == [
        "Chuyển đi",
        "Ở lại",
    ]


async def test_a_lesson_from_another_course_cannot_be_dragged_in(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    section = await add_section(api_client, course, owner, "Một")
    category = Category(name="Khác", slug=f"khac-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()
    other_course = (
        await api_client.post(
            COURSES,
            json={"title": "Khóa khác", "category_id": str(category.id)},
            headers=owner,
        )
    ).json()
    other_section = await add_section(api_client, other_course, owner, "Chương khác")
    stranger = await add_lesson(api_client, other_section, owner, "Bài lạ")

    response = await api_client.put(
        f"/api/v1/sections/{section['id']}/lessons/order",
        json={"lesson_ids": [stranger["id"]]},
        headers=owner,
    )

    assert response.status_code == 400


# --- Who may touch the curriculum ------------------------------------------


async def test_another_instructor_cannot_add_a_section(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    other = await sign_in(
        api_client, await make_user(db_session, "instructor", "khac@example.com")
    )

    response = await api_client.post(
        f"{COURSES}/{course['id']}/sections", json={"title": "Chen ngang"}, headers=other
    )

    assert response.status_code == 403


async def test_another_instructor_cannot_reorder_your_lessons(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    section = await add_section(api_client, course, owner, "Một")
    lesson = await add_lesson(api_client, section, owner, "Bài 1")
    other = await sign_in(
        api_client, await make_user(db_session, "instructor", "khac@example.com")
    )

    response = await api_client.put(
        f"/api/v1/sections/{section['id']}/lessons/order",
        json={"lesson_ids": [lesson["id"]]},
        headers=other,
    )

    assert response.status_code == 403


async def test_editing_the_curriculum_requires_signing_in(
    api_client: AsyncClient, course: dict
) -> None:
    response = await api_client.post(
        f"{COURSES}/{course['id']}/sections", json={"title": "Ẩn danh"}
    )

    assert response.status_code == 401


# --- Who may read it -------------------------------------------------------


async def test_the_curriculum_of_a_draft_is_private(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    await add_section(api_client, course, owner, "Mở đầu")
    student = await sign_in(api_client, await make_user(db_session, "student"))

    response = await api_client.get(
        f"{COURSES}/{course['id']}/curriculum", headers=student
    )

    assert response.status_code == 404


async def test_the_curriculum_of_a_published_course_is_public(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """The table of contents is what convinces someone to enrol."""
    section = await add_section(api_client, course, owner, "Mở đầu")
    await add_lesson(api_client, section, owner, "Bài 1")
    await api_client.post(f"{COURSES}/{course['id']}/submit", headers=owner)

    response = await api_client.get(f"{COURSES}/{course['id']}/curriculum")

    assert response.status_code == 200
    assert response.json()["sections"][0]["lessons"][0]["title"] == "Bài 1"


async def test_the_public_curriculum_does_not_hand_out_the_content(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """A table of contents lists what is inside; it does not open the box."""
    section = await add_section(api_client, course, owner, "Mở đầu")
    lesson = await add_lesson(api_client, section, owner, "Bài 1")
    await api_client.patch(
        f"/api/v1/lessons/{lesson['id']}",
        json={"article_content": "Nội dung trả tiền mới được đọc"},
        headers=owner,
    )
    await api_client.post(f"{COURSES}/{course['id']}/submit", headers=owner)

    body = (await api_client.get(f"{COURSES}/{course['id']}/curriculum")).text

    assert "Nội dung trả tiền mới được đọc" not in body


async def test_the_owner_reads_a_lesson_in_full(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    section = await add_section(api_client, course, owner, "Mở đầu")
    lesson = await add_lesson(
        api_client, section, owner, "Bài 1", article_content="# Nội dung"
    )

    response = await api_client.get(f"/api/v1/lessons/{lesson['id']}", headers=owner)

    assert response.status_code == 200
    assert response.json()["article_content"] == "# Nội dung"


async def test_a_stranger_cannot_read_a_lesson_of_a_draft(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    section = await add_section(api_client, course, owner, "Mở đầu")
    lesson = await add_lesson(api_client, section, owner, "Bài 1")
    student = await sign_in(api_client, await make_user(db_session, "student"))

    response = await api_client.get(f"/api/v1/lessons/{lesson['id']}", headers=student)

    assert response.status_code == 404


async def test_a_preview_lesson_is_readable_by_anyone(
    api_client: AsyncClient, course: dict, owner: dict[str, str]
) -> None:
    """`is_preview` is the sample chapter: readable without enrolling."""
    section = await add_section(api_client, course, owner, "Mở đầu")
    lesson = await add_lesson(
        api_client,
        section,
        owner,
        "Bài học thử",
        is_preview=True,
        article_content="Đọc thử được",
    )
    await api_client.post(f"{COURSES}/{course['id']}/submit", headers=owner)

    response = await api_client.get(f"/api/v1/lessons/{lesson['id']}")

    assert response.status_code == 200
    assert response.json()["article_content"] == "Đọc thử được"


async def test_a_non_preview_lesson_stays_shut_for_outsiders(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    """Enrolment is what opens it, and that is next week's feature."""
    section = await add_section(api_client, course, owner, "Mở đầu")
    lesson = await add_lesson(api_client, section, owner, "Bài trả phí")
    await api_client.post(f"{COURSES}/{course['id']}/submit", headers=owner)
    student = await sign_in(api_client, await make_user(db_session, "student"))

    response = await api_client.get(f"/api/v1/lessons/{lesson['id']}", headers=student)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LESSON_LOCKED"


# --- The database keeps its own promises -----------------------------------


async def test_two_sections_cannot_share_a_position(
    db_session: AsyncSession, course: dict
) -> None:
    """Deferred is not disabled: the constraint still fires, just later.

    `SET CONSTRAINTS ALL IMMEDIATE` is what forces the check here and now --
    which is also the proof that it was deferred, since an immediate constraint
    would already have raised on the INSERT above.
    """
    course_id = uuid.UUID(course["id"])
    db_session.add_all(
        [
            CourseSection(course_id=course_id, title="A", position=0),
            CourseSection(course_id=course_id, title="B", position=0),
        ]
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))

    await db_session.rollback()


async def test_the_curriculum_survives_a_course_being_deleted(
    api_client: AsyncClient,
    db_session: AsyncSession,
    course: dict,
    owner: dict[str, str],
) -> None:
    """Courses are soft-deleted, so CASCADE never fires and paid students keep
    their lessons."""
    section = await add_section(api_client, course, owner, "Mở đầu")

    await api_client.delete(f"{COURSES}/{course['id']}", headers=owner)

    assert await db_session.get(CourseSection, uuid.UUID(section["id"])) is not None
    rows = await db_session.scalars(
        select(CourseSection).where(CourseSection.course_id == uuid.UUID(course["id"]))
    )
    assert len(list(rows)) == 1
