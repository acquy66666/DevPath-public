"""Certificates of completion: when one is issued, what it says, who can see it.

A certificate is issued **once**, in the transaction that finishes the course,
and what it says is **frozen** there -- the name and the course title on it do
not follow later edits. Its code is **the only key** the public page takes, so
it has to be unguessable. The PDF is drawn afterwards by a worker, and until it
has been the certificate is still valid: it just has nothing to download yet.

Tests that draw a real PDF need Pango (WeasyPrint's layout engine). They skip
on a machine without it -- the Windows host -- and fail in CI, which installs
it; run them locally inside the backend container.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CERTIFICATE_CODE_ALPHABET,
    CERTIFICATE_CODE_LENGTH,
    Certificate,
    Course,
    Enrollment,
    User,
)
from app.services import certificates
from app.services.storage import get_storage
from tests.api.fakes import FakeStorage
from tests.api.test_progress import enrol, make_course, make_user, progress_url, sign_in


def pdf_engine_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except OSError:
        return False
    return True


needs_pdf_engine = pytest.mark.skipif(
    not pdf_engine_available() and not os.getenv("CI"),
    reason="WeasyPrint cần Pango: chạy trong container (`docker compose exec backend pytest`).",
)


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    user = await make_user(db_session, "instructor")
    user.full_name = "Trần Minh Khoa"
    return user


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    user = await make_user(db_session, "student")
    user.full_name = "Nguyễn Thị Ánh"
    return user


@pytest.fixture
def storage(app) -> FakeStorage:
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


async def finish(
    client: AsyncClient, session: AsyncSession, owner: User, student: User, lessons: int = 2
) -> tuple[Course, list, dict]:
    """A course of `lessons` videos, the student enrolled and through all of them."""
    course, rows = await make_course(session, owner, lessons=lessons)
    headers = await sign_in(client, student)
    await enrol(client, course, headers)
    for lesson in rows:
        response = await client.put(
            progress_url(lesson), json={"last_position_s": 10, "completed": True}, headers=headers
        )
        assert response.status_code == 200, response.text
    return course, rows, headers


async def certificates_of(session: AsyncSession, student: User) -> list[Certificate]:
    rows = await session.scalars(
        select(Certificate)
        .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
        .where(Enrollment.user_id == student.id)
    )
    return list(rows)


# --- Issuing -----------------------------------------------------------------


async def test_finishing_the_last_lesson_issues_one_certificate(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    student: User,
    rendered_certificates: list,
) -> None:
    course, _, _ = await finish(api_client, db_session, owner, student)

    [certificate] = await certificates_of(db_session, student)
    enrollment = await db_session.get(Enrollment, certificate.enrollment_id)
    assert certificate.recipient_name == "Nguyễn Thị Ánh"
    assert certificate.course_title == course.title
    assert certificate.instructor_name == "Trần Minh Khoa"
    assert certificate.issued_at == enrollment.completed_at
    # Drawn afterwards, by the worker -- asked for only once the row committed.
    assert certificate.pdf_key is None
    assert rendered_certificates == [certificate.id]


async def test_a_course_half_done_has_no_certificate(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, rows = await make_course(db_session, owner, lessons=2)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    await api_client.put(
        progress_url(rows[0]), json={"last_position_s": 10, "completed": True}, headers=headers
    )

    assert await certificates_of(db_session, student) == []


async def test_finishing_again_after_unticking_is_the_same_certificate(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    student: User,
    rendered_certificates: list,
) -> None:
    """Unticking a lesson takes the course's completion back, but not the
    certificate: it was true on the day it was issued, and it is still valid."""
    _, rows, headers = await finish(api_client, db_session, owner, student)
    [first] = await certificates_of(db_session, student)

    await api_client.put(
        progress_url(rows[-1]), json={"last_position_s": 10, "completed": False}, headers=headers
    )
    assert [c.code for c in await certificates_of(db_session, student)] == [first.code]

    await api_client.put(
        progress_url(rows[-1]), json={"last_position_s": 10, "completed": True}, headers=headers
    )
    assert [c.code for c in await certificates_of(db_session, student)] == [first.code]
    assert rendered_certificates == [first.id]


async def test_a_certificate_keeps_the_name_it_was_issued_to(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _, _ = await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)

    student.full_name = "Tên Mới"
    course.title = "Tựa đề mới"
    await db_session.flush()

    body = (await api_client.get(f"/api/v1/certificates/{certificate.code}")).json()
    assert body["recipient_name"] == "Nguyễn Thị Ánh"
    assert body["course_title"] != "Tựa đề mới"


async def test_the_code_is_sixteen_unambiguous_characters() -> None:
    codes = {certificates.new_code() for _ in range(200)}

    assert len(codes) == 200
    for code in codes:
        assert len(code) == CERTIFICATE_CODE_LENGTH
        assert set(code) <= set(CERTIFICATE_CODE_ALPHABET)
        assert not set(code) & set("IO01")


async def test_the_table_refuses_a_code_outside_the_alphabet(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)

    certificate.code = "abcdefghjkmnpqrs"
    with pytest.raises(IntegrityError, match="ck_certificates_code_format"):
        await db_session.flush()


async def test_a_code_that_is_already_taken_is_drawn_again(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    student: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """80 random bits do not collide in practice; the retry is there so that
    "in practice" is not the only thing standing between two learners and one
    certificate page."""
    other = await make_user(db_session, "student")
    await finish(api_client, db_session, owner, other)
    [taken] = await certificates_of(db_session, other)

    drawn = iter([taken.code, "Z" * CERTIFICATE_CODE_LENGTH])
    monkeypatch.setattr(certificates, "new_code", lambda: next(drawn))
    await finish(api_client, db_session, owner, student)

    [mine] = await certificates_of(db_session, student)
    assert mine.code == "Z" * CERTIFICATE_CODE_LENGTH


async def test_passing_the_last_quiz_issues_it_too(
    api_client: AsyncClient, db_session: AsyncSession, student: User
) -> None:
    """Completion is one function whichever kind of lesson finished it."""
    from tests.api.test_gamification import make_course as make_mixed_course
    from tests.api.test_gamification import sit_quiz

    mixed = await make_mixed_course(db_session, await make_user(db_session, "instructor"))
    db_session.add(Enrollment(user_id=student.id, course_id=mixed.course.id))
    await db_session.flush()
    headers = await sign_in(api_client, student)
    await api_client.put(
        progress_url(mixed.video), json={"last_position_s": 1, "completed": True}, headers=headers
    )
    await api_client.put(
        progress_url(mixed.code_lesson),
        json={"last_position_s": 1, "completed": True},
        headers=headers,
    )
    assert await certificates_of(db_session, student) == []

    await sit_quiz(api_client, mixed.quiz, headers, [1, 0])

    assert len(await certificates_of(db_session, student)) == 1


# --- The public page ------------------------------------------------------------


async def test_anybody_with_the_code_can_verify_it(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _, _ = await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)

    response = await api_client.get(f"/api/v1/certificates/{certificate.code}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == certificate.code
    assert body["recipient_name"] == "Nguyễn Thị Ánh"
    assert body["instructor_name"] == "Trần Minh Khoa"
    assert body["course_slug"] == course.slug
    assert body["pdf_ready"] is False
    assert student.email not in response.text


async def test_a_code_typed_with_dashes_or_in_lowercase_still_verifies(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)
    typed = "-".join(certificate.code[i : i + 4] for i in range(0, 16, 4)).lower()

    response = await api_client.get(f"/api/v1/certificates/{typed}")

    assert response.status_code == 200
    assert response.json()["code"] == certificate.code


@pytest.mark.parametrize("code", ["ZZZZZZZZZZZZZZZZ", "short", "I" * 16, "ABCD'; DROP TABLE x;--"])
async def test_an_unknown_or_malformed_code_is_not_found(
    api_client: AsyncClient, code: str
) -> None:
    """Malformed and unknown get the same answer: a malformed one never
    reaches the database, and neither says which of the two it was."""
    response = await api_client.get(f"/api/v1/certificates/{code}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CERTIFICATE_NOT_FOUND"


async def test_a_course_no_longer_on_sale_is_named_but_not_linked(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _, _ = await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)
    course.deleted_at = datetime.now(UTC)
    await db_session.flush()

    body = (await api_client.get(f"/api/v1/certificates/{certificate.code}")).json()

    assert body["course_slug"] is None
    assert body["course_title"] == certificate.course_title


# --- The PDF --------------------------------------------------------------------


async def test_a_pdf_not_drawn_yet_is_asked_for_again(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    student: User,
    storage: FakeStorage,
    rendered_certificates: list,
) -> None:
    """If the job was lost -- the broker was down when the course was
    finished -- the first person to want the PDF puts it back in the queue."""
    await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)
    rendered_certificates.clear()

    response = await api_client.get(f"/api/v1/certificates/{certificate.code}/pdf")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CERTIFICATE_NOT_READY"
    assert rendered_certificates == [certificate.id]


async def test_a_drawn_pdf_is_served_from_storage(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    student: User,
    storage: FakeStorage,
) -> None:
    await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)
    certificate.pdf_key = certificates.pdf_key(certificate.code)
    storage.objects[certificate.pdf_key] = (b"%PDF-1.7 fake", "application/pdf")
    await db_session.flush()

    response = await api_client.get(f"/api/v1/certificates/{certificate.code}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert certificate.code in response.headers["content-disposition"]
    assert response.content == b"%PDF-1.7 fake"


def test_the_page_escapes_what_people_typed() -> None:
    """A name is whatever somebody typed into their profile. WeasyPrint is not
    a browser, but markup in a name would still break the layout."""
    html = certificates.build_html(
        code="ABCDEFGHJKLMNPQR",
        recipient_name="<b>Ánh</b> & co",
        course_title="Python <cơ bản>",
        instructor_name="Khoa",
        issued_on=datetime(2026, 9, 28, tzinfo=UTC).date(),
        verify_url="https://devpath.example/cert/ABCDEFGHJKLMNPQR",
    )

    assert "<b>Ánh</b>" not in html
    assert "&lt;b&gt;Ánh&lt;/b&gt; &amp; co" in html
    assert "Python &lt;cơ bản&gt;" in html
    assert "ABCD-EFGH-JKLM-NPQR" in html
    assert "https://devpath.example/cert/ABCDEFGHJKLMNPQR" in html
    assert "<svg" in html  # the QR code, inline
    assert "28/09/2026" in html


@needs_pdf_engine
async def test_the_worker_draws_the_pdf_once(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)
    storage = FakeStorage()

    drew = await certificates.render(db_session, storage, certificate.id)
    again = await certificates.render(db_session, storage, certificate.id)

    assert (drew, again) == (True, False)
    await db_session.refresh(certificate)
    data, content_type = storage.objects[certificate.pdf_key]
    assert content_type == "application/pdf"
    assert data.startswith(b"%PDF-")


# --- Where the learner finds it -------------------------------------------------


async def test_my_courses_and_the_learning_page_carry_the_code(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _, headers = await finish(api_client, db_session, owner, student)
    [certificate] = await certificates_of(db_session, student)

    mine = (await api_client.get("/api/v1/enrollments/me", headers=headers)).json()
    progress = (
        await api_client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    ).json()

    assert [item["certificate_code"] for item in mine["items"]] == [certificate.code]
    assert progress["certificate_code"] == certificate.code


async def test_no_certificate_means_a_null_code(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    course, _ = await make_course(db_session, owner, lessons=2)
    headers = await sign_in(api_client, student)
    await enrol(api_client, course, headers)

    mine = (await api_client.get("/api/v1/enrollments/me", headers=headers)).json()

    assert [item["certificate_code"] for item in mine["items"]] == [None]


async def test_the_certificate_never_reaches_somebody_else(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, student: User
) -> None:
    """The code is on the learner's own lists only; nothing hands one learner
    another's code except that learner sharing it."""
    course, _, _ = await finish(api_client, db_session, owner, student)
    other = await make_user(db_session, "student")
    other_headers = await sign_in(api_client, other)
    await enrol(api_client, course, other_headers)

    mine = (await api_client.get("/api/v1/enrollments/me", headers=other_headers)).json()

    assert [item["certificate_code"] for item in mine["items"]] == [None]
    assert uuid.UUID(mine["items"][0]["course"]["id"]) == course.id
