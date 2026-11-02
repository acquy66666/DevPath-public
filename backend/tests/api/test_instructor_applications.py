"""Applying to teach: a learner asks, an admin decides.

What must hold: applying changes no role; only an approval does, and it tells
the learner; a rejection needs a reason the learner can read, and they may try
again; one application waits at a time; nobody but a student may apply, and
nobody but an admin may decide.
"""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InstructorApplication, Notification, User
from tests.api.publishing import make_admin
from tests.api.test_admin_users import make_user, sign_in

MINE = "/api/v1/users/me/instructor-application"
QUEUE = "/api/v1/admin/instructor-applications"


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await make_admin(db_session)


@pytest.fixture
async def admin(api_client: AsyncClient, admin_user: User) -> dict[str, str]:
    return await sign_in(api_client, admin_user)


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session, "student", "Trần Thị Học")


@pytest.fixture
async def learner(api_client: AsyncClient, student: User) -> dict[str, str]:
    return await sign_in(api_client, student)


async def role_of(session: AsyncSession, user: User) -> str:
    await session.refresh(user)
    return user.role


async def apply(client: AsyncClient, headers: dict[str, str], **body) -> dict:
    response = await client.post(MINE, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- The learner's side ----------------------------------------------------


async def test_applying_files_a_request_and_changes_no_role(
    api_client: AsyncClient, db_session: AsyncSession, student: User, learner: dict
) -> None:
    body = await apply(api_client, learner, motivation="  Em dạy Python ở trung tâm.  ")

    assert body["status"] == "pending"
    assert body["motivation"] == "Em dạy Python ở trung tâm."
    assert body["rejection_reason"] is None
    assert body["decided_at"] is None
    assert await role_of(db_session, student) == "student"

    mine = (await api_client.get(MINE, headers=learner)).json()
    assert mine["application"]["id"] == body["id"]


async def test_a_blank_introduction_is_no_introduction(
    api_client: AsyncClient, learner: dict
) -> None:
    assert (await apply(api_client, learner, motivation="   "))["motivation"] is None
    assert (await api_client.get(MINE, headers=learner)).json()["application"]["motivation"] is None


async def test_never_applied_answers_null(api_client: AsyncClient, learner: dict) -> None:
    response = await api_client.get(MINE, headers=learner)

    assert response.status_code == 200
    assert response.json() == {"application": None}


async def test_one_application_waits_at_a_time(
    api_client: AsyncClient, db_session: AsyncSession, student: User, learner: dict
) -> None:
    await apply(api_client, learner)

    response = await api_client.post(MINE, json={}, headers=learner)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INSTRUCTOR_APPLICATION_PENDING"
    rows = await db_session.scalars(
        select(InstructorApplication).where(InstructorApplication.user_id == student.id)
    )
    assert len(rows.all()) == 1


async def test_an_instructor_has_nothing_to_apply_for(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await make_user(db_session, "instructor")
    response = await api_client.post(MINE, json={}, headers=await sign_in(api_client, teacher))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ALREADY_INSTRUCTOR"


async def test_an_admin_is_not_quietly_demoted(
    api_client: AsyncClient, admin_user: User, admin: dict, db_session: AsyncSession
) -> None:
    response = await api_client.post(MINE, json={}, headers=admin)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ROLE_CHANGE_NOT_ALLOWED"
    assert await role_of(db_session, admin_user) == "admin"


async def test_an_introduction_has_a_length_limit(api_client: AsyncClient, learner: dict) -> None:
    response = await api_client.post(MINE, json={"motivation": "a" * 2001}, headers=learner)

    assert response.status_code == 422


async def test_signing_in_is_required(api_client: AsyncClient) -> None:
    assert (await api_client.get(MINE)).status_code == 401
    assert (await api_client.post(MINE, json={})).status_code == 401


async def test_the_old_self_promotion_is_gone(
    api_client: AsyncClient, db_session: AsyncSession, student: User, learner: dict
) -> None:
    """One click used to make anybody an instructor. It must not any more."""
    response = await api_client.post("/api/v1/users/me/instructor", headers=learner)

    assert response.status_code in (404, 405)
    assert await role_of(db_session, student) == "student"


# --- The admin's queue -----------------------------------------------------


async def test_the_queue_is_oldest_first_and_names_the_applicant(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, learner: dict
) -> None:
    first_sent = await apply(api_client, learner, motivation="Thư giới thiệu")
    later = await make_user(db_session, "student", "Người Đến Sau")
    await apply(api_client, await sign_in(api_client, later))
    # Both rows were written inside the test's one transaction, where now()
    # does not move: give the first one the earlier time it would have had.
    earlier = await db_session.get(InstructorApplication, uuid.UUID(first_sent["id"]))
    earlier.created_at -= timedelta(minutes=5)
    await db_session.flush()

    body = (await api_client.get(QUEUE, headers=admin)).json()

    assert body["total"] == 2
    first, second = body["items"]
    assert first["applicant"]["full_name"] == "Trần Thị Học"
    assert first["applicant"]["email"].endswith("@example.com")
    assert first["motivation"] == "Thư giới thiệu"
    assert first["enrollments_count"] == 0
    assert first["earlier_rejections"] == 0
    assert second["applicant"]["full_name"] == "Người Đến Sau"


async def test_the_queue_filters_and_searches(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, learner: dict
) -> None:
    mine = await apply(api_client, learner)
    other = await make_user(db_session, "student", "Lê Văn Khác")
    await apply(api_client, await sign_in(api_client, other))
    await api_client.post(f"{QUEUE}/{mine['id']}/approve", headers=admin)

    pending = (await api_client.get(QUEUE, headers=admin)).json()
    assert [item["applicant"]["full_name"] for item in pending["items"]] == ["Lê Văn Khác"]

    approved = (await api_client.get(QUEUE, params={"status": "approved"}, headers=admin)).json()
    assert [item["id"] for item in approved["items"]] == [mine["id"]]

    found = (
        await api_client.get(QUEUE, params={"status": "all", "q": "văn khác"}, headers=admin)
    ).json()
    assert found["total"] == 1


async def test_the_summary_counts_waiting_applications(
    api_client: AsyncClient, admin: dict, learner: dict
) -> None:
    before = (await api_client.get("/api/v1/admin/summary", headers=admin)).json()
    await apply(api_client, learner)
    after = (await api_client.get("/api/v1/admin/summary", headers=admin)).json()

    assert after["pending_instructor_applications"] == before["pending_instructor_applications"] + 1


async def test_only_an_admin_decides(
    api_client: AsyncClient, db_session: AsyncSession, student: User, learner: dict
) -> None:
    application = await apply(api_client, learner)
    teacher = await make_user(db_session, "instructor")
    headers = await sign_in(api_client, teacher)

    assert (await api_client.get(QUEUE, headers=headers)).status_code == 403
    response = await api_client.post(f"{QUEUE}/{application['id']}/approve", headers=learner)
    assert response.status_code == 403
    assert await role_of(db_session, student) == "student"


# --- Deciding --------------------------------------------------------------


async def test_approving_makes_an_instructor_and_tells_them(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict,
    student: User,
    learner: dict,
) -> None:
    application = await apply(api_client, learner)
    assert (
        await api_client.get("/api/v1/instructor/qa-threads", headers=learner)
    ).status_code == 403

    response = await api_client.post(f"{QUEUE}/{application['id']}/approve", headers=admin)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["decided_at"] is not None
    assert await role_of(db_session, student) == "instructor"

    told = await db_session.scalar(select(Notification).where(Notification.user_id == student.id))
    assert told.type == "instructor_application_approved"
    assert told.payload == {"application_id": application["id"]}

    # The role is read from the database, so the token already held works.
    assert (
        await api_client.get("/api/v1/instructor/qa-threads", headers=learner)
    ).status_code == 200
    mine = (await api_client.get(MINE, headers=learner)).json()["application"]
    assert mine["status"] == "approved"


async def test_rejecting_needs_a_reason_the_learner_reads(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict,
    student: User,
    learner: dict,
) -> None:
    application = await apply(api_client, learner)
    url = f"{QUEUE}/{application['id']}/reject"

    assert (await api_client.post(url, json={}, headers=admin)).status_code == 422
    assert (await api_client.post(url, json={"reason": "   "}, headers=admin)).status_code == 422

    response = await api_client.post(
        url, json={"reason": " Cần giới thiệu kinh nghiệm dạy. "}, headers=admin
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert await role_of(db_session, student) == "student"

    mine = (await api_client.get(MINE, headers=learner)).json()["application"]
    assert mine["status"] == "rejected"
    assert mine["rejection_reason"] == "Cần giới thiệu kinh nghiệm dạy."

    told = await db_session.scalar(select(Notification).where(Notification.user_id == student.id))
    assert told.type == "instructor_application_rejected"
    assert told.payload["reason"] == "Cần giới thiệu kinh nghiệm dạy."


async def test_after_a_rejection_the_learner_may_try_again(
    api_client: AsyncClient, admin: dict, learner: dict
) -> None:
    first = await apply(api_client, learner)
    await api_client.post(f"{QUEUE}/{first['id']}/reject", json={"reason": "Thiếu"}, headers=admin)

    second = await apply(api_client, learner, motivation="Bổ sung kinh nghiệm")

    assert second["id"] != first["id"]
    mine = (await api_client.get(MINE, headers=learner)).json()["application"]
    assert mine["id"] == second["id"]
    queue = (await api_client.get(QUEUE, headers=admin)).json()
    assert queue["items"][0]["earlier_rejections"] == 1


async def test_a_decision_is_made_once(api_client: AsyncClient, admin: dict, learner: dict) -> None:
    application = await apply(api_client, learner)
    await api_client.post(f"{QUEUE}/{application['id']}/approve", headers=admin)

    again = await api_client.post(f"{QUEUE}/{application['id']}/approve", headers=admin)
    reject = await api_client.post(
        f"{QUEUE}/{application['id']}/reject", json={"reason": "Muộn rồi"}, headers=admin
    )

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "INSTRUCTOR_APPLICATION_DECIDED"
    assert reject.status_code == 409


async def test_an_unknown_application_is_404(api_client: AsyncClient, admin: dict) -> None:
    response = await api_client.post(f"{QUEUE}/{uuid.uuid4()}/approve", headers=admin)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "INSTRUCTOR_APPLICATION_NOT_FOUND"


async def test_approving_does_not_overwrite_a_role_changed_meanwhile(
    api_client: AsyncClient,
    db_session: AsyncSession,
    admin: dict,
    student: User,
    learner: dict,
) -> None:
    application = await apply(api_client, learner)
    student.role = "admin"
    await db_session.flush()

    response = await api_client.post(f"{QUEUE}/{application['id']}/approve", headers=admin)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ROLE_CHANGE_NOT_ALLOWED"
    assert await role_of(db_session, student) == "admin"
